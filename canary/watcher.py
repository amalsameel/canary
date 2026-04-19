"""filesystem watchdog with debouncing, drift checks, and sensitive-file guards."""
import datetime
import os
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from .binary import looks_binary
from .checkpoint import take_snapshot
from .config import load_config
from .drift import cosine_similarity
from .ibm.embeddings import get_embedding
from .risk import bar_color, render_risk_bar
from .sensitive_files import is_sensitive
from .session import log_event
from .ui import BRAND, command_bar, console, divider, fail, fields, hero, note, ok, warn

EVENT_SYMBOLS = {
    "modified": "◆",
    "created": "✦",
    "deletion": "✕",
}


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _drift_bar(drift: float) -> str:
    score = max(0, min(100, int(drift * 200)))
    filled = max(0, min(20, round(score / 5)))
    color = bar_color(score)
    return f"[{color}]{'█' * filled}{'░' * (20 - filled)}[/{color}]  [{color}]{drift:.4f}[/{color}]"


def _drift_status(drift: float, threshold: float) -> str:
    if drift > threshold:
        return f"[bold red]■  alert[/bold red]  [dim](> {threshold})[/dim]"
    if drift > threshold * 0.5:
        return "[yellow]▲  review[/yellow]"
    if drift > 0.0:
        return f"[{BRAND}]●  stable[/{BRAND}]"
    return "[dim]●  match[/dim]"


class CanaryHandler(FileSystemEventHandler):
    def __init__(self, baseline: dict[str, list[float]], cfg: dict, target: str):
        self.baseline = baseline
        self.cfg = cfg
        self.target = os.path.abspath(target)
        self.recent_changes: list[float] = []
        self._last_event: dict[str, float] = {}
        self.last_activity: float = time.time()
        self.event_count: int = 0
        self.drift_alerts: int = 0

    def on_modified(self, event):
        if not event.is_directory:
            self._dispatch(event.src_path, "modified")

    def on_created(self, event):
        if not event.is_directory:
            self._dispatch(event.src_path, "created")

    def on_deleted(self, event):
        if event.is_directory or self._should_ignore(event.src_path):
            return

        rel = os.path.relpath(event.src_path, self.target)
        console.print(f"  [dim]{_ts()}[/dim]  [red]{EVENT_SYMBOLS['deletion']}[/red]  [white]{rel}[/white]")
        render_risk_bar(60, "deletion")
        console.print()
        log_event("deletion", {"file": rel}, target=self.target)

    def _should_ignore(self, path: str) -> bool:
        abspath = os.path.abspath(path)
        canary_dir = os.path.join(self.target, ".canary")
        if abspath.startswith(canary_dir + os.sep) or abspath == canary_dir:
            return True

        parts = set(Path(abspath).parts)
        if parts & set(self.cfg["ignore_dirs"]):
            return True

        ext = os.path.splitext(abspath)[1].lower()
        return ext in self.cfg["ignore_exts"]

    def _debounce(self, path: str) -> bool:
        now = time.time()
        last = self._last_event.get(path, 0.0)
        if now - last < 0.3:
            return False
        self._last_event[path] = now
        return True

    def _dispatch(self, path: str, event_type: str):
        if self._should_ignore(path) or not self._debounce(path):
            return

        rel = os.path.relpath(path, self.target)

        if is_sensitive(path, self.cfg["sensitive_patterns"]):
            console.print()
            divider("sensitive file")
            console.print()
            fail(f"{event_type} · {rel}")
            console.print()
            render_risk_bar(85, "risk")
            console.print()
            try:
                confirm = input("  continue? [y/n]  ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = "n"

            console.print()
            if confirm != "y":
                fail("blocked", "the file is already on disk, so stop the agent now")
            else:
                warn("continuing")
            console.print()
            log_event("sensitive_file_access", {"file": rel, "event": event_type}, target=self.target)
            return

        try:
            size = os.path.getsize(path)
        except OSError:
            return

        if size > self.cfg["max_file_size_bytes"]:
            log_event("skipped_large_file", {"file": rel, "size": size}, target=self.target)
            return

        if looks_binary(path):
            log_event("skipped_binary_file", {"file": rel}, target=self.target)
            return

        now = time.time()
        window = self.cfg["change_rate_window"]
        self.recent_changes = [t for t in self.recent_changes if now - t < window]
        self.recent_changes.append(now)
        if len(self.recent_changes) > self.cfg["change_rate_limit"]:
            console.print(f"  [dim]{_ts()}[/dim]  [yellow]▲[/yellow]  [yellow]{len(self.recent_changes)} changes in {window}s[/yellow]")
            render_risk_bar(55, "change rate")
            console.print()
            log_event("change_rate_alert", {"count": len(self.recent_changes)}, target=self.target)

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read()
        except OSError as exc:
            note(f"could not read {rel}: {exc}")
            return

        if not content.strip():
            return

        try:
            new_embedding = get_embedding(content)
        except Exception as exc:
            note(f"embedding failed for {rel}: {exc}")
            return

        symbol = EVENT_SYMBOLS.get(event_type, "◆")
        color = BRAND if event_type == "created" else "white"
        console.print(f"  [dim]{_ts()}  │[/dim]  [{color}]{symbol}[/{color}]  [white]{rel}[/white]")

        baseline_embedding = self.baseline.get(path)
        if baseline_embedding is not None:
            similarity = cosine_similarity(baseline_embedding, new_embedding)
            drift = round(1 - similarity, 4)
            filename = os.path.basename(path)
            threshold = self.cfg["drift_entry_point"] if filename in self.cfg["entry_points"] else self.cfg["drift_alert"]
            console.print(f"            [dim]╰─  drift[/dim]  {_drift_bar(drift)}  {_drift_status(drift, threshold)}")

            if drift > threshold:
                log_event("drift_alert", {"file": rel, "drift": drift, "threshold": threshold}, target=self.target)
        else:
            note("baseline captured")

        self.baseline[path] = new_embedding
        self.last_activity = time.time()
        self.event_count += 1
        if drift > threshold if baseline_embedding is not None else False:
            self.drift_alerts += 1
        log_event(event_type, {"file": rel}, target=self.target)
        console.print()


def _build_baseline(target: str, cfg: dict) -> tuple[dict[str, list[float]], int]:
    baseline: dict[str, list[float]] = {}
    skipped = 0
    target = os.path.abspath(target)

    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in cfg["ignore_dirs"]]
        for fname in files:
            path = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext in cfg["ignore_exts"]:
                continue
            if is_sensitive(path, cfg["sensitive_patterns"]):
                continue

            try:
                if os.path.getsize(path) > cfg["max_file_size_bytes"]:
                    continue
            except OSError:
                continue

            if looks_binary(path):
                continue

            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    content = handle.read()
            except OSError:
                continue

            if not content.strip():
                continue

            try:
                baseline[path] = get_embedding(content)
            except Exception:
                skipped += 1

    return baseline, skipped


def _mode_label() -> str:
    local = os.environ.get("IBM_LOCAL", "false").lower() == "true"
    if local:
        return f"[{BRAND}]local[/{BRAND}]  [dim](on-device granite · M1 GPU)[/dim]"
    return f"[{BRAND}]online[/{BRAND}]  [dim](managed cloud inference · watsonx.ai)[/dim]"


def _make_observer():
    if sys.platform == "darwin":
        return PollingObserver(timeout=1.0), True
    return Observer(), False


_AUDIT_EVENTS_PATH = Path.home() / ".canary" / "audit_events.jsonl"


def _wait_for_session(continuous: bool) -> bool:
    """Block until a new audit-hook event appears (agent has started).

    Returns True when a session is detected, False if interrupted.
    In continuous mode, skip waiting and return True immediately.
    """
    if continuous:
        return True

    start_pos = _AUDIT_EVENTS_PATH.stat().st_size if _AUDIT_EVENTS_PATH.exists() else 0

    console.print(
        f"  [bold {BRAND}]◉[/bold {BRAND}]  "
        f"ready  ·  waiting for agent session to begin"
    )
    console.print(
        f"  [dim]╰─  monitoring activates on the first tool call[/dim]"
    )
    console.print()

    try:
        while True:
            time.sleep(0.4)
            if not _AUDIT_EVENTS_PATH.exists():
                continue
            if _AUDIT_EVENTS_PATH.stat().st_size > start_pos:
                return True
    except KeyboardInterrupt:
        return False


def start_watch(target: str, *, idle_timeout: int = 0):
    """Watch *target* for agent activity.

    idle_timeout > 0: exit automatically after that many seconds of no file events.
    idle_timeout == 0: run until Ctrl-C (continuous mode).
    """
    continuous = idle_timeout == 0
    target = os.path.abspath(target)
    cfg = load_config(target)
    mode = "continuous" if continuous else "next session"
    hero(subtitle=f"{_mode_label()}  [dim]·  {mode}[/dim]", path=target)
    command_bar("watch")

    if not _wait_for_session(continuous):
        note("watch cancelled")
        console.print()
        return

    with console.status("[dim]indexing workspace...[/dim]", spinner="dots"):
        baseline, skipped = _build_baseline(target, cfg)
        checkpoint_id = take_snapshot(target)

    idle_detail = f"exits after {idle_timeout}s idle" if not continuous else "Ctrl-C to stop"
    ok("session detected", f"{len(baseline)} files indexed  ·  monitoring active")
    if skipped and not baseline:
        warn("drift detection disabled", "embedding API unavailable — run `canary mode local` or check credentials")
    elif skipped:
        note(f"{skipped} file(s) skipped — drift detection may be incomplete")
    fields([("checkpoint", checkpoint_id), ("mode", idle_detail)])

    observer, using_polling = _make_observer()
    if using_polling:
        note("using polling on macos")

    console.print()
    divider()
    console.print()

    handler = CanaryHandler(baseline, cfg, target)
    observer.schedule(handler, target, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(0.5)
            if not continuous and (time.time() - handler.last_activity) >= idle_timeout:
                break
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
    observer.join()

    console.print()
    if not continuous:
        note(f"session ended  ·  {handler.event_count} file event(s)  ·  {handler.drift_alerts} drift alert(s)")
    else:
        note("watch stopped")
    console.print()
