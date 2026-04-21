"""click cli entrypoint."""
from collections.abc import Callable
from contextlib import nullcontext, redirect_stderr, redirect_stdout
import datetime
import io
import json as _json
import os
import re
import select
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

_AUDIT_EVENTS_PATH = Path.home() / ".canary" / "audit_events.jsonl"


def _append_audit_event(event: dict) -> None:
    try:
        _AUDIT_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_AUDIT_EVENTS_PATH, "a") as f:
            f.write(_json.dumps({"timestamp": time.time(), **event}) + "\n")
    except Exception:
        pass

import click
from dotenv import dotenv_values, load_dotenv, set_key
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

load_dotenv()
os.environ["IBM_LOCAL"] = "true"

from . import __version__
from .claude_transcript import (
    CLAUDE_PROJECTS_DIR,
    CODEX_SESSIONS_DIR,
    iter_bash_tool_uses,
    iter_tool_results,
    read_jsonl_since,
    tool_result_state,
)
from .checkpoint import delete_all_checkpoints, delete_checkpoint, list_checkpoints, rollback as do_rollback, take_snapshot
from .device import detect_device_profile
from .docs_topics import DOC_TOPICS
from .frontend import FRONTEND_CATALOG, ShellSessionState, prompt_segments
from .guard import default_shim_dir, get_enabled, guard_records, install_guard, remove_guard, resolve_real_binary, set_enabled
from .local_embeddings import ensure_local_model, install_local_dependencies, local_model_cached, missing_local_dependencies
from .prompt_firewall import scan_prompt
from .risk import compute_risk_score, render_findings, SEVERITY_COLOR, SEVERITY_ICON
from .semantic_firewall import semantic_scan
from .session import log_event, read_log
from .ui import (
    ACCENT,
    BRAND,
    ERROR,
    MUTED,
    PROMPT_IDLE,
    SEARCH_SURFACE,
    TRACE,
    WHITE,
    animate_pipeline,
    animate_surveillance,
    command_bar,
    console,
    default_shell_tips,
    fail,
    fields,
    hero,
    note,
    ok,
    prompt_rules,
    prompt_preview,
    protected_prompt_panel,
    result_panel,
    shell_frame_width,
    shell_scene,
    show_watch_panel,
    SubprocessLog,
    subprocess_overview_log,
    live_activity_text,
    warn,
)
from .watcher import start_watch

EVENT_COLORS = {
    "prompt_scan": BRAND,
    "modified": "white",
    "created": BRAND,
    "deletion": "red",
    "drift_alert": "red",
    "sensitive_file_access": "bold red",
    "change_rate_alert": "yellow",
    "skipped_large_file": "dim",
    "skipped_binary_file": "dim",
}

EVENT_LABELS = {
    "prompt_scan": "prompt review",
    "modified": "modified",
    "created": "created",
    "deletion": "deleted",
    "drift_alert": "drift alert",
    "sensitive_file_access": "sensitive file",
    "change_rate_alert": "change burst",
    "skipped_large_file": "skipped",
    "skipped_binary_file": "skipped",
}

SHELL_COMMANDS: list[tuple[str, str]] = FRONTEND_CATALOG.rows()

_EDITOR_SUGGESTION_ROWS = len(SHELL_COMMANDS)

ENV_TEMPLATE = """# canary runs IBM Granite locally on this machine.
IBM_LOCAL=true

# optional: move the local model cache somewhere with more disk space.
# HF_HOME=~/.cache/huggingface
"""


class LowerHelpFormatter(click.HelpFormatter):
    def write_usage(self, prog: str, args: str = "", prefix: str = "Usage: ") -> None:
        super().write_usage(prog, args, prefix.lower())

    def write_heading(self, heading: str) -> None:
        super().write_heading(heading.lower())


class LowerContext(click.Context):
    formatter_class = LowerHelpFormatter


class LowerCommand(click.Command):
    context_class = LowerContext

    def get_help_option(self, ctx):
        option = super().get_help_option(ctx)
        if option is not None:
            option.help = "show this message and exit."
        return option


class LowerGroup(click.Group):
    context_class = LowerContext
    command_class = LowerCommand

    def get_help_option(self, ctx):
        option = super().get_help_option(ctx)
        if option is not None:
            option.help = "show this message and exit."
        return option


def _recent_line(message: str) -> str:
    stamp = datetime.datetime.now().strftime("%H:%M")
    return f"{stamp}  ·  {message}"


def _resolve_primary_agent() -> tuple[str | None, str | None]:
    for agent in ("claude", "codex"):
        real_binary = resolve_real_binary(agent)
        if real_binary and os.access(real_binary, os.X_OK):
            return agent, real_binary
        fallback = shutil.which(agent)
        if fallback:
            return agent, fallback
    return None, None


def _resolve_named_agent(agent: str) -> tuple[str | None, str | None]:
    real_binary = resolve_real_binary(agent)
    if real_binary and os.access(real_binary, os.X_OK):
        return agent, real_binary
    fallback = shutil.which(agent)
    if fallback:
        return agent, fallback
    return None, None


def _render_shell_home(
    recent_activity: list[str],
    *,
    prompt: str = "",
    submitted: bool = False,
    spinner: str = "❯",
    status=None,
    launch_target: str = "no launch target",
) -> None:
    console.clear()
    console.print(_shell_home_renderable(
        recent_activity,
        prompt=prompt,
        submitted=submitted,
        spinner=spinner,
        status=status,
        launch_target=launch_target,
        show_prompt_lane=False,
    ))


def _shell_home_renderable(
    recent_activity: list[str],
    *,
    prompt: str = "",
    submitted: bool = False,
    spinner: str = "❯",
    status: RenderableType | None = None,
    launch_target: str = "no launch target",
    show_prompt_lane: bool = True,
) -> RenderableType:
    editor_suggestions = None
    if show_prompt_lane:
        editor_suggestions = _editor_suggestion_renderable(prompt, width=shell_frame_width() - 2)
    return shell_scene(
        cwd=os.getcwd(),
        screening_enabled=get_enabled(),
        recent_activity=recent_activity,
        launch_target=launch_target,
        prompt=prompt,
        submitted=submitted,
        spinner=spinner,
        status=status,
        tips=default_shell_tips(),
        show_prompt_lane=show_prompt_lane,
        editor_suggestions=editor_suggestions,
    )


def _print_home() -> None:
    _render_shell_home([
        _recent_line("screening starts on by default in the interactive shell"),
        _recent_line("try /agent to set the coding agent you are working with"),
    ])
    note("run this command in a real terminal to use the interactive shell")
    console.print()


@click.group(cls=LowerGroup, invoke_without_command=True)
@click.version_option(__version__, prog_name="canary", help="show the version and exit.")
@click.pass_context
def cli(ctx):
    """canary — ai agent watchdog."""
    if ctx.invoked_subcommand is None:
        if sys.stdin.isatty() and sys.stdout.isatty():
            _set_local_mode(True)
            set_enabled(True)
            _interactive_shell()
            return
        _print_home()


def _confirm(prompt: str, default: str = "n") -> bool:
    try:
        answer = input(f"  {prompt} [y/n]  ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = default
    return answer == "y"


def _env_path() -> Path:
    return Path(os.getcwd()) / ".env"


def _write_env_if_missing() -> bool:
    env_path = _env_path()
    if env_path.exists():
        return False
    env_path.write_text(ENV_TEMPLATE)
    return True


def _set_local_mode(enabled: bool) -> None:
    env_path = _env_path()
    if not env_path.exists():
        env_path.write_text(ENV_TEMPLATE)
    set_key(str(env_path), "IBM_LOCAL", "true" if enabled else "false", quote_mode="never")
    os.environ["IBM_LOCAL"] = "true" if enabled else "false"


def _enable_local_mode(*, allow_slow: bool, install_if_missing: bool, download_if_missing: bool) -> bool:
    profile = detect_device_profile()
    if profile.local_warning and not allow_slow:
        warn("local mode may run exceptionally slower on this device", profile.summary)
        if not _confirm("continue?"):
            fail("local setup cancelled")
            console.print()
            return False

    missing = missing_local_dependencies()
    if missing:
        warn("local support is not installed", ", ".join(missing))
        if not install_if_missing:
            fail("local mode not enabled", "run `canary setup` or install local support first")
            console.print()
            return False
        if not _confirm("install local support now?"):
            fail("local mode not enabled")
            console.print()
            return False
        with console.status("[dim]installing local support...[/dim]", spinner="dots"):
            install_local_dependencies()

    if not local_model_cached():
        detail = "first run downloads the Granite model"
        if profile.local_warning:
            detail = f"{detail}  ·  {profile.summary}"
        warn("local model is not cached", detail)
        if not download_if_missing:
            fail("local mode not enabled", "download the model first")
            console.print()
            return False
        if not _confirm("download the local Granite model now?"):
            fail("local mode not enabled")
            console.print()
            return False
        with console.status("[dim]downloading local model...[/dim]", spinner="dots"):
            ensure_local_model(download_if_needed=True)

    _set_local_mode(True)
    ok("local mode", "on-device granite ready")
    if profile.local_warning:
        warn("this will run exceptionally slower on this device", profile.summary)
    console.print()
    return True


def _auto_setup_backend(prefer: str) -> str:
    del prefer
    return "local"


def _review_prompt(text: str, *, target: str, render_clear: bool = True, show_status: bool = True) -> tuple[list, int]:
    findings = scan_prompt(text)
    if show_status:
        with console.status("[dim]reviewing...[/dim]", spinner="dots"):
            findings += semantic_scan(text)
    else:
        findings += semantic_scan(text)

    score = compute_risk_score(findings)
    if findings or render_clear:
        render_findings(findings, score)

    log_event("prompt_scan", {
        "score": score,
        "finding_count": len(findings),
        "severities": [f.severity for f in findings],
    }, target=target)
    return findings, score


def _shell_pause(prompt: str = "press enter to return") -> None:
    try:
        input(f"  {prompt}")
    except (EOFError, KeyboardInterrupt):
        pass


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi_sequences(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


def _render_captured_output(text: str, *, max_lines: int = 28) -> RenderableType | None:
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return None

    truncated = len(lines) > max_lines
    visible = lines[-max_lines:]
    rendered: list[RenderableType] = []
    if truncated:
        rendered.append(Text.from_markup(f"[dim]showing last {max_lines} line(s)[/dim]"))
        rendered.append(Text(""))
    rendered.extend(Text.from_ansi(line) for line in visible)
    return Group(*rendered)


def _run_embedded_command_capture(args: list[str]) -> tuple[int, RenderableType | None]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with console.capture() as captured_console:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            code = _run_embedded_command(args)
    captured = "\n".join(
        part.rstrip()
        for part in (captured_console.get(), stdout_buffer.getvalue(), stderr_buffer.getvalue())
        if part.strip()
    )
    return code, _render_captured_output(captured)


def _kv_table(rows: list[tuple[str, str]]) -> RenderableType:
    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True)
    table.add_column()
    for label, value in rows:
        value_renderable = Text.from_markup(value) if "[" in value else Text(value, style=WHITE)
        table.add_row(Text(label, style=f"dim {MUTED}"), value_renderable)
    return table


def _checkpoints_table(target: str = ".") -> RenderableType:
    checkpoints = list_checkpoints(target)
    if not checkpoints:
        return Text.from_markup("[dim]no snapshots yet[/dim]")

    table = Table(
        show_header=True,
        header_style="dim",
        box=None,
        padding=(0, 2),
        pad_edge=False,
    )
    table.add_column("#", style="dim", width=4, no_wrap=True)
    table.add_column("type", width=8, no_wrap=True)
    table.add_column("id", width=36, no_wrap=True)
    table.add_column("saved", style="dim")

    for index, checkpoint in enumerate(checkpoints, 1):
        saved = datetime.datetime.fromtimestamp(checkpoint["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        cid = checkpoint["id"]
        if cid.startswith("rollback_backup"):
            kind, color, icon = "backup", "dim", "◆"
        elif cid.startswith("checkpoint_"):
            kind, color, icon = "auto", "dim", "◆"
        else:
            kind, color, icon = "named", BRAND, "✦"
        table.add_row(
            str(index),
            f"[{color}]{icon}  {kind}[/{color}]",
            f"[{color}]{cid}[/{color}]",
            saved,
        )
    return table


def _checkpoints_shell_renderable(target: str = ".", *, footer: str | None = None) -> RenderableType:
    rows: list[RenderableType] = [
        Text.from_markup(f"[bold {ACCENT}]restore points[/bold {ACCENT}]"),
        _checkpoints_table(target),
    ]
    if footer:
        rows.extend((Text(""), Text.from_markup(f"[dim]{footer}[/dim]")))
    else:
        rows.extend((
            Text(""),
            Text.from_markup("[dim]/checkpoint <name>  ·  save a named snapshot[/dim]"),
            Text.from_markup("[dim]/checkpoint <name> delete  ·  remove a named snapshot[/dim]"),
            Text.from_markup("[dim]/rollback [name]  ·  restore a snapshot[/dim]"),
        ))
    return Group(*rows)


def _session_log_renderable(target: str = ".", *, tail: int | None = None) -> RenderableType:
    events = read_log(target)
    if tail:
        events = events[-tail:]

    if not events:
        return Group(
            Text.from_markup(f"[bold {ACCENT}]session log[/bold {ACCENT}]"),
            Text.from_markup("[dim]no events yet[/dim]"),
        )

    table = Table(
        show_header=True,
        header_style="dim",
        box=None,
        padding=(0, 2),
        pad_edge=False,
    )
    table.add_column("time", style="dim", width=10, no_wrap=True)
    table.add_column("event", width=16, no_wrap=True)
    table.add_column("file", width=32, no_wrap=True)
    table.add_column("detail", style="dim")

    for event in events:
        timestamp = datetime.datetime.fromtimestamp(event["timestamp"]).strftime("%H:%M:%S")
        event_type = event["type"]
        color = EVENT_COLORS.get(event_type, "white")
        label = EVENT_LABELS.get(event_type, event_type.replace("_", " "))
        rest = {k: v for k, v in event.items() if k not in ("timestamp", "type")}

        file_col = rest.get("file", "")
        detail_parts = []
        if "drift" in rest:
            detail_parts.append(f"drift {rest['drift']:.4f}")
        if "threshold" in rest:
            detail_parts.append(f"thr {rest['threshold']}")
        if "count" in rest:
            detail_parts.append(f"{rest['count']} files")
        if "score" in rest:
            detail_parts.append(f"score {rest['score']}")
        if "finding_count" in rest:
            detail_parts.append(f"{rest['finding_count']} findings")
        if "event" in rest:
            detail_parts.append(rest["event"])
        if not detail_parts and not file_col:
            detail_parts = [_json.dumps(rest)] if rest else []

        table.add_row(
            timestamp,
            f"[{color}]{label}[/{color}]",
            f"[dim]{file_col}[/dim]",
            "  ·  ".join(detail_parts),
        )

    scope = f"last {tail}" if tail else "full"
    return Group(
        Text.from_markup(f"[bold {ACCENT}]session log[/bold {ACCENT}]"),
        Text.from_markup(f"[dim]scope  {scope}  ·  {len(events)} event(s)[/dim]"),
        Text(""),
        table,
    )


def _docs_shell_renderable(topic: str | None = None) -> RenderableType:
    if topic is None:
        table = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False)
        table.add_column(width=12, no_wrap=True, style=f"bold {BRAND}")
        table.add_column()
        for name, info in DOC_TOPICS.items():
            table.add_row(name, info["summary"])
        return Group(
            Text.from_markup(f"[bold {ACCENT}]built-in docs[/bold {ACCENT}]"),
            table,
            Text(""),
            Text.from_markup("[dim]/docs <topic>  ·  open a topic inline[/dim]"),
        )

    lines = [Text.from_markup(f"[bold {ACCENT}]docs {topic}[/bold {ACCENT}]"), Text("")]
    lines.extend(Text.from_markup(line) if "[" in line else Text(line) for line in DOC_TOPICS[topic]["lines"])
    return Group(*lines)


def _guard_status_renderable() -> RenderableType:
    shim_dir = default_shim_dir()
    records = guard_records()
    if not records:
        return Group(
            Text.from_markup(f"[bold {ACCENT}]guard status[/bold {ACCENT}]"),
            Text.from_markup("[dim]no direct guard shims installed[/dim]"),
            Text(""),
            Text.from_markup(f'[dim]export PATH="{shim_dir}:$PATH"[/dim]'),
        )

    enabled = get_enabled()
    state_color = BRAND if enabled else "yellow"
    rows = [
        ("shim dir", str(shim_dir)),
        ("screening", f"[{state_color}]{'on' if enabled else 'off'}[/{state_color}]"),
    ]
    body: list[RenderableType] = [
        Text.from_markup(f"[bold {ACCENT}]guard status[/bold {ACCENT}]"),
        _kv_table(rows),
        Text(""),
    ]
    for agent, record in records.items():
        body.append(Text.from_markup(f"[bold white]{agent}[/bold white]  [dim]{record.shim_path}[/dim]"))
        body.append(Text.from_markup(f"[dim]real  {record.real_binary}[/dim]"))
        if record.watch:
            body.append(Text.from_markup("[dim]watch enabled[/dim]"))
        body.append(Text(""))
    body.append(Text.from_markup(f'[dim]export PATH="{shim_dir}:$PATH"[/dim]'))
    return Group(*body)


def _setup_shell_renderable() -> RenderableType:
    profile = detect_device_profile()
    deps = missing_local_dependencies()
    return Group(
        Text.from_markup(f"[bold {ACCENT}]local setup[/bold {ACCENT}]"),
        _kv_table([
            ("device", profile.summary),
            ("runtime", "local only"),
            ("deps", "ready" if not deps else ", ".join(deps)),
            ("model", "cached" if local_model_cached() else "not cached"),
        ]),
        Text(""),
        Text.from_markup("[dim]the interactive shell already starts in local mode[/dim]"),
        Text.from_markup("[dim]run `canary setup` directly if you want the full provisioning flow[/dim]"),
    )


def _tail_file_lines(path: Path, *, limit: int = 5) -> list[str]:
    try:
        if not path.exists():
            return []
        lines = [_strip_ansi_sequences(line.rstrip()) for line in path.read_text(errors="ignore").splitlines()]
    except OSError:
        return []
    return [line for line in lines if line.strip()][-limit:]


class _WatchShellBody:
    def __init__(self, target: str, *, idle: int, continuous: bool) -> None:
        self.target = os.path.abspath(target)
        self.idle = idle
        self.continuous = continuous
        self.started_at = time.time()

    def __rich__(self) -> RenderableType:
        frame = int(time.time() * 8)
        pid = _watch_already_running()
        status_line = Text("  ")
        if pid is not None:
            status_line.append_text(live_activity_text("watching", frame))
            status_line.append("  ·  repo drift monitor live", style=f"dim {MUTED}")
        else:
            status_line.append("watch exited", style=f"bold {ERROR}")
            status_line.append("  ·  run /watch to start again", style=f"dim {MUTED}")

        mode = "continuous" if self.continuous else f"idle {self.idle}s"
        runtime = f"{int(max(0, time.time() - self.started_at))}s"
        rows: list[RenderableType] = [
            status_line,
            _kv_table([
                ("target", self.target),
                ("pid", str(pid) if pid is not None else "not running"),
                ("mode", mode),
                ("runtime", runtime),
                ("log", str(_WATCH_LOG_PATH)),
            ]),
        ]

        tail_lines = _tail_file_lines(_WATCH_LOG_PATH, limit=4)
        if tail_lines:
            rows.extend((
                Text(""),
                Text.from_markup(f"[dim]recent watch output[/dim]"),
                *(Text(line, style=f"dim {WHITE}") for line in tail_lines),
            ))

        rows.extend((
            Text(""),
            Text.from_markup("[dim]/watch exit  ·  stop this subprocess[/dim]"),
        ))
        return Group(*rows)


class _AuditShellBody:
    def __init__(self) -> None:
        self.current_requests: dict[str, dict] = {}
        self.past_requests: list[dict] = []
        self.offset = _AUDIT_EVENTS_PATH.stat().st_size if _AUDIT_EVENTS_PATH.exists() else 0
        self.remainder = ""
        self.last_event_time = time.time()

    def _poll(self) -> None:
        self.offset, self.remainder, entries = read_jsonl_since(_AUDIT_EVENTS_PATH, self.offset, self.remainder)
        saw_activity = False
        for event in entries:
            if not isinstance(event, dict):
                continue
            _record_audit_dashboard_event(event, self.current_requests, self.past_requests)
            saw_activity = True
        if saw_activity:
            self.last_event_time = time.time()

    def __rich__(self) -> RenderableType:
        self._poll()
        frame = int(time.time() * 8)
        return Group(
            _audit_dashboard_renderable(
                self.current_requests,
                self.past_requests,
                last_event_time=self.last_event_time,
                frame=frame,
            ),
            Text.from_markup("[dim]/audit exit  ·  close this subprocess[/dim]"),
        )


class _ShellSubprocessView:
    def __init__(
        self,
        session_state: ShellSessionState,
        *,
        command_log: SubprocessLog | None = None,
        body: RenderableType | None = None,
        active_step: str | None = None,
    ) -> None:
        self.session_state = session_state
        self.command_log = command_log
        self.body = body
        self.active_step = active_step if active_step in {"shield", "audit", "watch", "launch"} else None

    def __rich__(self) -> RenderableType:
        overview_log = subprocess_overview_log(
            screening_enabled=get_enabled(),
            audit_active=self.session_state.audit_active,
            watch_active=self.session_state.watch_active,
            watch_target=self.session_state.watch_target,
            launch_target=self.session_state.launch_label,
            active_step=self.active_step,
            audit_external=self.session_state.audit_external,
        )

        status_block: RenderableType
        if self.command_log is not None:
            status_block = self.command_log.merged(overview_log, animated=False).render()
        else:
            status_block = overview_log.render()

        blocks: list[RenderableType] = [status_block]

        if self.body is not None and not (
            isinstance(self.body, _AuditShellBody) and self.session_state.audit_tmux_pane
        ):
            blocks.append(Text(""))
            blocks.append(self.body)
        elif self.session_state.audit_tmux_pane:
            blocks.extend((
                Text(""),
                Text.from_markup("[dim]live audit is attached in the current tmux terminal pane[/dim]"),
            ))
        return Group(*blocks)


def _shell_command_name(raw: str) -> str | None:
    if not raw.startswith("/"):
        return None
    try:
        tokens = shlex.split(raw[1:].strip())
    except ValueError:
        return None
    return tokens[0].lower() if tokens else None


def _watch_shell_options(args: list[str]) -> tuple[str, int, bool, bool, bool]:
    target = "."
    idle = 30
    continuous = False
    stop_requested = False
    log_requested = False

    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg == "--stop":
            stop_requested = True
        elif arg == "--log":
            log_requested = True
        elif arg == "--continuous":
            continuous = True
        elif arg == "--idle":
            idx += 1
            if idx >= len(args):
                raise ValueError("missing value for `--idle`")
            try:
                idle = int(args[idx])
            except ValueError as exc:
                raise ValueError("`--idle` expects an integer value") from exc
            if idle < 0:
                raise ValueError("`--idle` must be 0 or greater")
        elif arg.startswith("--idle="):
            try:
                idle = int(arg.split("=", 1)[1])
            except ValueError as exc:
                raise ValueError("`--idle` expects an integer value") from exc
            if idle < 0:
                raise ValueError("`--idle` must be 0 or greater")
        elif arg.startswith("-"):
            raise ValueError(f"unknown watch option: `{arg}`")
        elif target == ".":
            target = arg
        else:
            raise ValueError(f"unexpected watch argument: `{arg}`")
        idx += 1

    return target, idle, continuous, stop_requested, log_requested


def _parse_checkpoint_shell_args(args: list[str]) -> tuple[str, str | None]:
    if not args:
        raise ValueError("checkpoint name required  ·  use `/checkpoint <name>`")

    normalized = [arg.lower() for arg in args]
    if normalized == ["list"]:
        return "list", None
    if normalized in (["delete", "all"], ["all", "delete"]):
        return "delete-all", None
    if normalized == ["exit"]:
        return "exit", None
    if len(args) == 1:
        return "create", args[0]
    if len(args) == 2 and normalized[0] == "delete":
        return "delete", args[1]
    if len(args) == 2 and normalized[1] == "delete":
        return "delete", args[0]
    raise ValueError("use `/checkpoint <name>`, `/checkpoint <name> delete`, or `/checkpoint list`")


def _bash_permission_allow_rules(settings: dict | None = None) -> list[str]:
    active_settings = settings if settings is not None else _load_claude_settings()
    allow = active_settings.get("permissions", {}).get("allow", [])
    if not isinstance(allow, list):
        return []
    return [
        entry
        for entry in allow
        if isinstance(entry, str) and entry.startswith("Bash(")
    ]


def _bash_permissions_renderable(settings: dict | None = None) -> tuple[RenderableType, int]:
    rules = _bash_permission_allow_rules(settings)
    rows: list[RenderableType] = [
        Text.from_markup(f"[bold {ACCENT}]always allowed bash commands[/bold {ACCENT}]"),
        Text.from_markup(f"[dim]settings  {_CLAUDE_SETTINGS_PATH}[/dim]"),
    ]
    if not rules:
        rows.append(Text.from_markup("[dim]no always-allowed Bash rules found[/dim]"))
        return Group(*rows), 0

    rows.append(Text.from_markup(f"[dim]{len(rules)} rule(s) from permissions.allow[/dim]"))
    for rule in rules:
        rows.append(Text(rule, style=WHITE))
    return Group(*rows), len(rules)


def _slash_command_matches(buffer: str, *, limit: int = 6) -> list[tuple[str, str]]:
    if not buffer.startswith("/"):
        return []
    return FRONTEND_CATALOG.slash_matches(buffer, limit=limit)


def _searchable_entries(buffer: str, *, limit: int = _EDITOR_SUGGESTION_ROWS) -> list[tuple[str, str]]:
    return FRONTEND_CATALOG.search(buffer, limit=limit)


def _ansi_color(hex_color: str, *, bold: bool = False, dim: bool = False, background: bool = False) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    attrs: list[str] = []
    if bold:
        attrs.append("1")
    if dim:
        attrs.append("2")
    attrs.append(f"{48 if background else 38};2;{r};{g};{b}")
    return f"\x1b[{';'.join(attrs)}m"


_ANSI_RESET = "\x1b[0m"
_ANSI_BRAND = _ansi_color(BRAND)
_ANSI_BRAND_BOLD = _ansi_color(BRAND, bold=True)
_ANSI_WHITE = _ansi_color(WHITE)
_ANSI_PROMPT_BG = _ansi_color(PROMPT_IDLE, background=True)
_ANSI_SEARCH_BG = _ansi_color(SEARCH_SURFACE, background=True)


def _editor_rule(width: int) -> str:
    return f"{_ANSI_WHITE}{'─' * width}{_ANSI_RESET}"


def _editor_input_line(buffer: str, *, prefix_symbol: str, width: int) -> str:
    visible = buffer
    available = max(8, width - 3)
    if len(visible) > available:
        visible = "…" + visible[-(available - 1):]
    cursor = "▌"
    content = f"{prefix_symbol} {visible}{cursor}"
    padding = max(0, width - len(content))
    parts = [f"{_ANSI_WHITE}{_ANSI_PROMPT_BG}{prefix_symbol} {_ANSI_RESET}"]
    for segment, highlight in prompt_segments(visible):
        # If buffer doesn't start with "/", always use white (not brand color)
        if not buffer.startswith("/"):
            style = _ANSI_WHITE
        else:
            style = _ANSI_BRAND if highlight else _ANSI_WHITE
        parts.append(f"{style}{_ANSI_PROMPT_BG}{segment}{_ANSI_RESET}")
    parts.append(f"{_ANSI_BRAND_BOLD}{_ANSI_PROMPT_BG}{cursor}{_ANSI_RESET}")
    parts.append(f"{_ANSI_PROMPT_BG}{' ' * padding}{_ANSI_RESET}")
    return "".join(parts)


def _editor_suggestion_lines(buffer: str, *, width: int) -> list[str]:
    # Only show suggestions when buffer starts with "/"
    if not buffer.startswith("/"):
        return []
    matches = FRONTEND_CATALOG.search_matches(buffer, limit=_EDITOR_SUGGESTION_ROWS)
    lines: list[str] = []
    prefix_pad = 2
    label_width = max(len(label) for label, _ in SHELL_COMMANDS) + 2
    detail_width = max(10, width - prefix_pad - label_width - 1)
    for match in matches:
        label = match.command.name
        detail = match.detail
        trimmed = detail if len(detail) <= detail_width else detail[: detail_width - 1] + "…"
        visible_width = prefix_pad + label_width + 1 + len(trimmed)
        padding = max(0, width - visible_width)
        lines.append(
            f"{_ANSI_SEARCH_BG}{' ' * prefix_pad}{_ANSI_RESET}"
            f"{_ANSI_BRAND}{_ANSI_SEARCH_BG}{label:<{label_width}}{_ANSI_RESET}"
            f"{_ANSI_WHITE}{_ANSI_SEARCH_BG} {trimmed}{_ANSI_RESET}"
            f"{_ANSI_SEARCH_BG}{' ' * padding}{_ANSI_RESET}"
        )
    # Don't pad with empty lines - return only actual results
    return lines


def _editor_suggestion_renderable(buffer: str, *, width: int) -> RenderableType | None:
    rows = _editor_suggestion_lines(buffer, width=width)
    if not rows:
        return None
    return Group(*(Text.from_ansi(row) for row in rows))


class _PinnedShellBlock:
    def __init__(
        self,
        *,
        stream=None,
        width: int | None = None,
        color_system: str | None = None,
    ) -> None:
        self._stream = stream or sys.stdout
        self._width = width or console.width
        self._color_system = color_system or console.color_system or "truecolor"
        self._rows = 0
        self._mounted = False

    def _render_lines(self, renderable: RenderableType) -> list[str]:
        capture = io.StringIO()
        render_console = Console(
            file=capture,
            force_terminal=True,
            width=self._width,
            color_system=self._color_system,
            legacy_windows=False,
        )
        render_console.print(renderable, end="")
        return capture.getvalue().splitlines() or [""]

    def _paint(self, rows: list[str]) -> None:
        self._stream.write("\x1b[H\x1b[2J")
        self._write_rows(rows)
        self._stream.flush()
        self._rows = len(rows)

    def _write_rows(self, rows: list[str], *, min_rows: int = 0) -> None:
        row_count = max(len(rows), min_rows)
        padded = rows + [""] * (row_count - len(rows))
        for idx, row in enumerate(padded):
            self._stream.write("\r\x1b[2K" + row)
            if idx < row_count - 1:
                self._stream.write("\n")

    def mount(self, renderable: RenderableType) -> None:
        rows = self._render_lines(renderable)
        self._stream.write("\x1b[?1049h")
        self._paint(rows)
        self._mounted = True

    def update(self, renderable: RenderableType) -> None:
        if not self._mounted:
            self.mount(renderable)
            return
        rows = self._render_lines(renderable)
        self._paint(rows)

    def close(self) -> None:
        if not self._mounted:
            return
        self._stream.write("\x1b[?1049l")
        self._stream.flush()
        self._rows = 0
        self._mounted = False


def _read_prompt_line(prefix_symbol: str = "❯") -> str:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        top_rule, bottom_rule = prompt_rules()
        console.print(top_rule)
        try:
            raw = console.input(f"[bold white]{prefix_symbol}[/bold white] ").strip()
        finally:
            console.print(bottom_rule)
            console.print()
        return raw

    try:
        import termios
        import tty
    except ImportError:
        top_rule, bottom_rule = prompt_rules()
        console.print(top_rule)
        try:
            raw = console.input(f"[bold white]{prefix_symbol}[/bold white] ").strip()
        finally:
            console.print(bottom_rule)
            console.print()
        return raw

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    buffer: list[str] = []
    indent = "  "
    width = shell_frame_width() - len(indent)

    def _get_suggestion_rows() -> list[str]:
        return _editor_suggestion_lines("".join(buffer), width=width)

    def _get_block_rows() -> int:
        # 3 = rule + input line + rule, plus dynamic suggestion rows
        return 3 + len(_get_suggestion_rows())

    def _draw_editor() -> None:
        suggestion_rows = _get_suggestion_rows()
        rows = [
            indent + _editor_rule(width),
            indent + _editor_input_line("".join(buffer), prefix_symbol=prefix_symbol, width=width),
            indent + _editor_rule(width),
            *[indent + row for row in suggestion_rows],
        ]
        sys.stdout.write("\x1b[u")
        for idx, row in enumerate(rows):
            sys.stdout.write("\r\x1b[2K" + row)
            if idx < len(rows) - 1:
                sys.stdout.write("\n")
        sys.stdout.flush()

    try:
        tty.setraw(fd)
        sys.stdout.write("\x1b[?25l")
        # Reserve max space initially
        max_rows = 3 + _EDITOR_SUGGESTION_ROWS
        sys.stdout.write("\n" * (max_rows - 1))
        sys.stdout.write(f"\x1b[{max_rows - 1}F")
        sys.stdout.write("\x1b[s")
        _draw_editor()
        sys.stdout.flush()

        while True:
            char = sys.stdin.read(1)

            if char in ("\r", "\n"):
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                return "".join(buffer).strip()
            if char == "\x03":
                raise KeyboardInterrupt
            if char == "\x04":
                if not buffer:
                    raise EOFError
                continue
            if char in ("\x08", "\x7f"):
                if buffer:
                    buffer.pop()
                    _draw_editor()
                continue
            if char == "\x1b":
                next_char = sys.stdin.read(1)
                if next_char == "[":
                    sys.stdin.read(1)
                continue
            if char.isprintable():
                buffer.append(char)
            _draw_editor()
    finally:
        sys.stdout.write("\x1b[?25h")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _read_pinned_prompt_line(
    shell_block: _PinnedShellBlock,
    recent_activity: list[str],
    session_state: ShellSessionState,
    *,
    prefix_symbol: str = "❯",
    status: RenderableType | None = None,
) -> str:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return _read_prompt_line(prefix_symbol)

    try:
        import termios
        import tty
    except ImportError:
        return _read_prompt_line(prefix_symbol)

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    buffer: list[str] = []

    def _draw_shell() -> None:
        shell_block.update(_shell_home_renderable(
            recent_activity,
            prompt="".join(buffer),
            submitted=False,
            spinner=prefix_symbol,
            status=status,
            launch_target=session_state.launch_label,
            show_prompt_lane=True,
        ))

    try:
        tty.setraw(fd)
        sys.stdout.write("\x1b[?25l")
        _draw_shell()
        sys.stdout.flush()

        while True:
            ready, _, _ = select.select([fd], [], [], 0.12)
            if not ready:
                _draw_shell()
                continue

            char = sys.stdin.read(1)

            if char in ("\r", "\n"):
                return "".join(buffer).strip()
            if char == "\x03":
                raise KeyboardInterrupt
            if char == "\x04":
                if not buffer:
                    raise EOFError
                continue
            if char in ("\x08", "\x7f"):
                if buffer:
                    buffer.pop()
                    _draw_shell()
                continue
            if char == "\x1b":
                next_char = sys.stdin.read(1)
                if next_char == "[":
                    sys.stdin.read(1)
                continue
            if char.isprintable():
                buffer.append(char)
                _draw_shell()
    finally:
        sys.stdout.write("\x1b[?25h")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _run_embedded_command(args: list[str]) -> int:
    import click as _click

    try:
        cli.main(args=args, standalone_mode=False)
        return 0
    except _click.UsageError as e:
        _show_usage_error(e)
        return 2
    except _click.exceptions.Exit as e:
        return int(e.code or 0)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        return int(code)


def _parallel_terminals_enabled() -> bool:
    env_val = os.environ.get("CANARY_ALLOW_PARALLEL_TERMINALS", "").strip().lower()
    if env_val in {"0", "false", "no", "off"}:
        return False
    # Default to enabled on macOS
    return sys.platform == "darwin"


def _audit_inline_argv(*, parent_pid: int | None = None) -> list[str]:
    args = [
        sys.executable,
        "-m",
        "canary.cli",
        "audit",
        "--inline",
        "--dashboard",
    ]
    if parent_pid is not None:
        args.extend(["--parent-pid", str(parent_pid)])
    return args


def _launch_terminal_command(command: str, *, cwd: str, close_tab_on_exit: bool = False) -> bool:
    if not _parallel_terminals_enabled():
        return False
    if sys.platform != "darwin":
        return False

    shell_command = (
        f"cd {shlex.quote(cwd)}; "
        f"export PATH={shlex.quote(os.environ.get('PATH', ''))}; "
        f"{command}"
    )
    if close_tab_on_exit:
        shell_command = f"{shell_command}; exit"
    script = f'tell application "Terminal" to do script { _json.dumps(shell_command) }'

    try:
        subprocess.run(["osascript", "-e", script], check=True)
        return True
    except Exception:
        return False


def _launch_audit_terminal(*, parent_pid: int | None = None, close_tab_on_exit: bool = False) -> bool:
    return _launch_terminal_command(
        shlex.join(_audit_inline_argv(parent_pid=parent_pid)),
        cwd=os.getcwd(),
        close_tab_on_exit=close_tab_on_exit,
    )


def _launch_agent_terminal(agent_argv: list[str], *, cwd: str) -> bool:
    return _launch_terminal_command(shlex.join(agent_argv), cwd=cwd)


def _tmux_available() -> bool:
    return shutil.which("tmux") is not None


def _tmux_in_session() -> bool:
    return bool(os.environ.get("TMUX"))


def _tmux_run(
    args: list[str],
    *,
    capture_output: bool = False,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["tmux", *args],
        capture_output=capture_output,
        check=check,
        text=True,
    )


def _tmux_pane_exists(pane_id: str | None) -> bool:
    if not pane_id or not _tmux_available():
        return False
    result = _tmux_run(
        ["display-message", "-p", "-t", pane_id, "#{pane_id}"],
        capture_output=True,
    )
    return result.returncode == 0 and result.stdout.strip() == pane_id


def _close_tmux_pane(pane_id: str | None) -> bool:
    if not _tmux_pane_exists(pane_id):
        return False
    return _tmux_run(["kill-pane", "-t", pane_id]).returncode == 0


def _open_tmux_audit_pane(*, cwd: str, parent_pid: int | None = None) -> str | None:
    if not (_tmux_available() and _tmux_in_session()):
        return None

    result = _tmux_run(
        [
            "split-window",
            "-d",
            "-v",
            "-l",
            "14",
            "-P",
            "-F",
            "#{pane_id}",
            "-c",
            cwd,
            "sh",
            "-lc",
            shlex.join(_audit_inline_argv(parent_pid=parent_pid)),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    pane_id = result.stdout.strip()
    return pane_id or None


def _ensure_tmux_audit_pane(session_state: ShellSessionState, *, cwd: str) -> str | None:
    if _tmux_pane_exists(session_state.audit_tmux_pane):
        return session_state.audit_tmux_pane

    pane_id = _open_tmux_audit_pane(cwd=cwd, parent_pid=os.getpid())
    session_state.set_audit_tmux_pane(pane_id)
    return pane_id


def _run_agent_in_ephemeral_tmux_session(agent_argv: list[str], *, cwd: str) -> int | None:
    if not _tmux_available() or _tmux_in_session():
        return None

    session_name = f"canary-inline-{os.getpid()}-{int(time.time())}"
    exit_path = Path(tempfile.gettempdir()) / f"{session_name}.exit"
    exit_path.unlink(missing_ok=True)

    agent_command = shlex.join(agent_argv)
    audit_command = shlex.join(_audit_inline_argv(parent_pid=os.getpid()))
    session_name_q = shlex.quote(session_name)
    exit_path_q = shlex.quote(str(exit_path))
    agent_shell = (
        f"{agent_command}; "
        f"status=$?; "
        f"printf '%s' \"$status\" > {exit_path_q}; "
        f"tmux kill-session -t {session_name_q} >/dev/null 2>&1; "
        f"exit \"$status\""
    )

    try:
        _tmux_run(
            ["new-session", "-d", "-s", session_name, "-c", cwd, "sh", "-lc", agent_shell],
            check=True,
        )
        _tmux_run(
            [
                "split-window",
                "-d",
                "-v",
                "-t",
                f"{session_name}:0.0",
                "-l",
                "14",
                "-c",
                cwd,
                "sh",
                "-lc",
                audit_command,
            ],
            check=True,
        )
        _tmux_run(["select-pane", "-t", f"{session_name}:0.0"])
        attach_result = _tmux_run(["attach-session", "-t", session_name])
    except Exception:
        _tmux_run(["kill-session", "-t", session_name])
        raise

    try:
        return int(exit_path.read_text().strip())
    except (OSError, ValueError):
        return attach_result.returncode
    finally:
        exit_path.unlink(missing_ok=True)


def _handle_shell_command(
    raw: str,
    recent_activity: list[str],
    session_state: ShellSessionState,
    *,
    subprocess_log: SubprocessLog | None = None,
    refresh_status: Callable[[RenderableType | None], None] | None = None,
) -> tuple[bool, RenderableType | None]:
    command = raw[1:].strip()
    if not command:
        return True, subprocess_log.render() if subprocess_log else None

    command_name = raw.split()[0]
    if subprocess_log is None:
        subprocess_log = SubprocessLog(animated=False)
        subprocess_log.add(command_name, "processing request", "running")

    def _view(
        body: RenderableType | None = None,
        *,
        active_step: str | None = None,
    ) -> RenderableType:
        return _ShellSubprocessView(
            session_state,
            command_log=subprocess_log,
            body=body,
            active_step=active_step,
        )

    def _refresh(body: RenderableType | None = None, *, active_step: str | None = None) -> None:
        if refresh_status is not None:
            refresh_status(_view(body, active_step=active_step))

    def _complete(
        detail: str,
        body: RenderableType | None = None,
        *,
        active_step: str | None = None,
    ) -> tuple[bool, RenderableType]:
        subprocess_log.update(command_name, "complete", detail)
        _refresh(body, active_step=active_step)
        return True, _view(body)

    def _fail(
        detail: str,
        body: RenderableType | None = None,
    ) -> tuple[bool, RenderableType]:
        subprocess_log.update(command_name, "failed", detail)
        _refresh(body)
        return True, _view(body)

    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return _fail(str(exc))

    name, args = tokens[0].lower(), tokens[1:]

    if name in {"exit", "quit", "q"}:
        recent_activity.append(_recent_line("shell closed"))
        subprocess_log.update(command_name, "complete", "shell closed")
        _refresh()
        return False, _view()

    if name == "help":
        help_text = Group(
            Text.from_markup(f"[bold {ACCENT}]slash commands[/bold {ACCENT}]"),
            Text.from_markup("[white]/agent  /help  /status  /on  /off[/white]"),
            Text.from_markup("[white]/audit  /perms  /watch  /checkpoint[/white]"),
            Text.from_markup("[white]/rollback[/white]"),
            Text.from_markup("[white]/log  /checkpoints  /docs  /setup[/white]"),
            Text.from_markup("[white]/guard  /clear  /exit[/white]"),
            Text.from_markup("[dim]type plain text to screen it and launch it into your selected coding agent[/dim]"),
            Text.from_markup("[dim]use /agent first  ·  /watch stays off until you ask for repo drift surveillance[/dim]"),
        )
        recent_activity.append(_recent_line("opened command list"))
        return _complete("showed command list", help_text)

    if name == "status":
        recent_activity.append(_recent_line("inspected shell state"))
        return _complete(
            "loaded shell state",
            _kv_table([
                ("cwd", os.getcwd()),
                ("binary", session_state.launch_target_path or "none selected"),
            ]),
        )

    if name == "agent":
        if not args:
            available = []
            for candidate in ("claude", "codex"):
                found_name, found_path = _resolve_named_agent(candidate)
                if found_path:
                    available.append(f"{found_name}  ·  {found_path}")
            available_rows = [Text.from_markup(f"[dim]{row}[/dim]") for row in available]
            if not available_rows:
                available_rows = [Text.from_markup("[dim]no supported agent binaries found in PATH[/dim]")]
            status_text = Group(
                Text.from_markup(f"[bold {ACCENT}]launch target[/bold {ACCENT}]"),
                Text.from_markup(f"[dim]current[/dim]  [white]{session_state.launch_label}[/white]"),
                Text.from_markup("[dim]try `/agent claude`, `/agent codex`, or `/agent none`[/dim]"),
                *available_rows,
            )
            recent_activity.append(_recent_line("listed launch targets"))
            return _complete("listed available agents", status_text)

        target_name = args[0].lower()
        if target_name in {"none", "clear"}:
            session_state.clear_launch_target()
            recent_activity.append(_recent_line("cleared launch target"))
            return _complete("cleared launch target")

        found_name, found_path = _resolve_named_agent(target_name)
        if not found_path:
            return _fail(f"could not find `{target_name}` in PATH")

        session_state.set_launch_target(found_name or target_name, found_path)
        recent_activity.append(_recent_line(f"launch target set to {session_state.launch_label}"))
        return _complete(f"launch target set to {session_state.launch_label}")

    if name == "clear":
        recent_activity.clear()
        recent_activity.append(_recent_line("recent activity cleared"))
        return _complete("recent activity cleared")

    if name == "on":
        set_enabled(True)
        recent_activity.append(_recent_line("screening enabled"))
        return _complete("screening enabled")

    if name == "off":
        set_enabled(False)
        recent_activity.append(_recent_line("screening disabled"))
        return _complete("screening disabled")

    if name == "audit":
        if args and args[0].lower() in {"exit", "stop", "--stop"}:
            if _close_tmux_pane(session_state.audit_tmux_pane):
                recent_activity.append(_recent_line("audit tmux pane closed"))
            pid = _audit_already_running()
            if pid:
                os.kill(pid, 15)
                _AUDIT_PID_PATH.unlink(missing_ok=True)
            session_state.set_audit(False)
            recent_activity.append(_recent_line("audit subprocess closed"))
            return _complete("audit subprocess closed")

        if args:
            return _fail("use `/audit` or `/audit exit`")

        if _tmux_pane_exists(session_state.audit_tmux_pane):
            session_state.set_audit(True)
            recent_activity.append(_recent_line("audit tmux pane already live"))
            return _complete("live audit tmux pane active")

        # Try to launch a separate terminal window for audit (macOS only)
        terminal_launched = _launch_audit_terminal(parent_pid=os.getpid())
        if terminal_launched:
            recent_activity.append(_recent_line("audit terminal opened"))
            session_state.set_audit(True)
            return _complete("live audit terminal opened")

        # Fallback: spawn background audit process
        existing = _audit_already_running()
        if existing is None:
            _spawn_background_audit(parent_pid=os.getpid())
            recent_activity.append(_recent_line("audit subprocess started"))
        else:
            recent_activity.append(_recent_line("audit subprocess already running"))

        body = _AuditShellBody()
        subprocess_log.update(command_name, "running", "starting live audit subprocess")
        _refresh(body, active_step="audit")
        session_state.set_audit(True)
        return _complete("live audit subprocess active", body)

    if name == "perms":
        permissions_renderable, count = _bash_permissions_renderable()
        recent_activity.append(_recent_line("listed always-allowed Bash commands"))
        return _complete(f"loaded {count} always-allowed Bash rule(s)", permissions_renderable)

    if name == "watch":
        shell_args = ["--stop" if arg == "exit" else "--log" if arg == "log" else arg for arg in args]
        try:
            target, idle, continuous, stop_requested, log_requested = _watch_shell_options(shell_args)
        except ValueError as exc:
            return _fail(str(exc))

        if log_requested:
            recent_activity.append(_recent_line("viewed watch log"))
            tail_lines = _tail_file_lines(_WATCH_LOG_PATH, limit=10)
            body: RenderableType = Group(
                Text.from_markup(f"[bold {ACCENT}]watch log[/bold {ACCENT}]"),
                *(Text(line, style=f"dim {WHITE}") for line in tail_lines),
            ) if tail_lines else Group(
                Text.from_markup(f"[bold {ACCENT}]watch log[/bold {ACCENT}]"),
                Text.from_markup("[dim]no watch log found[/dim]"),
            )
            return _complete("loaded watch log", body)

        if stop_requested:
            pid = _watch_already_running()
            if pid:
                os.kill(pid, 15)
                _WATCH_PID_PATH.unlink(missing_ok=True)
                recent_activity.append(_recent_line("watch disarmed"))
                detail = "main-terminal watch stream stopped"
            else:
                recent_activity.append(_recent_line("watch already off"))
                detail = "watch already off"
            session_state.set_watch(False)
            return _complete(detail)

        watch_target = os.path.abspath(target)
        if not os.path.exists(watch_target):
            return _fail(f"watch target not found: {watch_target}")

        body = _WatchShellBody(watch_target, idle=idle, continuous=continuous)
        subprocess_log.update(command_name, "running", "starting watch subprocess")
        _refresh(body, active_step="watch")
        existing = _watch_already_running()
        if existing is None:
            existing = _spawn_background_watch(watch_target, idle=idle, continuous=continuous).pid
            recent_activity.append(_recent_line(f"watch armed for {watch_target}"))
            detail = "main-terminal watch stream live"
        else:
            recent_activity.append(_recent_line(f"watch active for {watch_target}"))
            detail = "main-terminal watch stream already live"

        session_state.set_watch(
            True,
            watch_target,
            idle_seconds=idle,
            continuous=continuous,
        )
        return _complete(detail, body)

    if name == "setup":
        recent_activity.append(_recent_line("reviewed local setup"))
        return _complete("loaded local setup", _setup_shell_renderable())

    if name == "guard":
        if args and args[0].lower() == "exit":
            return _complete("guard subprocess closed")
        subcommand = list(args) if args else ["status"]
        if subcommand == ["status"]:
            recent_activity.append(_recent_line("inspected guard status"))
            return _complete("loaded guard status", _guard_status_renderable())
        code, body = _run_embedded_command_capture(["guard", *subcommand])
        recent_activity.append(_recent_line(f"guard {' '.join(subcommand)}"))
        if code == 0:
            return _complete(f"guard {' '.join(subcommand)} completed", body)
        return _fail(f"guard {' '.join(subcommand)} failed", body)

    if name == "checkpoint":
        try:
            action, checkpoint_name = _parse_checkpoint_shell_args(args)
        except ValueError as exc:
            return _fail(str(exc), _checkpoints_shell_renderable())

        if action == "exit":
            return _complete("checkpoint subprocess closed")
        if action == "list":
            recent_activity.append(_recent_line("listed checkpoints"))
            return _complete("listed restore points", _checkpoints_shell_renderable())
        if action == "delete-all":
            deleted = delete_all_checkpoints(".")
            recent_activity.append(_recent_line(f"deleted {deleted} checkpoint(s)"))
            return _complete(
                f"deleted {deleted} checkpoint(s)" if deleted else "no checkpoints to delete",
                _checkpoints_shell_renderable(footer=f"{deleted} snapshot(s) deleted" if deleted else "no snapshots to delete"),
            )
        if action == "delete":
            if checkpoint_name is None:
                return _fail("checkpoint name required")
            if not delete_checkpoint(".", checkpoint_name):
                return _fail(f"checkpoint `{checkpoint_name}` not found", _checkpoints_shell_renderable())
            recent_activity.append(_recent_line(f"deleted checkpoint {checkpoint_name}"))
            return _complete(
                f"deleted checkpoint `{checkpoint_name}`",
                _checkpoints_shell_renderable(footer=f"deleted `{checkpoint_name}`"),
            )

        if checkpoint_name is None:
            return _fail("checkpoint name required")
        try:
            checkpoint_id = take_snapshot(".", checkpoint_name)
        except RuntimeError as exc:
            return _fail(str(exc), _checkpoints_shell_renderable())
        recent_activity.append(_recent_line(f"saved checkpoint {checkpoint_id}"))
        return _complete(
            f"saved checkpoint `{checkpoint_id}`",
            _checkpoints_shell_renderable(footer=f"saved `{checkpoint_id}`"),
        )

    if name == "rollback":
        if args and args[0].lower() == "exit":
            return _complete("rollback subprocess closed")
        if len(args) > 1:
            return _fail("use `/rollback` or `/rollback <name>`")
        checkpoint_id = args[0] if args else None
        try:
            restored, backup = do_rollback(".", checkpoint_id)
        except RuntimeError as exc:
            return _fail(str(exc), _checkpoints_shell_renderable(footer="create a named checkpoint first"))
        recent_activity.append(_recent_line(f"rolled back to {restored}"))
        return _complete(
            f"restored `{restored}`",
            Group(
                Text.from_markup(f"[bold {ACCENT}]rollback complete[/bold {ACCENT}]"),
                _kv_table([
                    ("restored", restored),
                    ("backup", backup),
                ]),
                Text(""),
                _checkpoints_shell_renderable(footer=f"backup saved as `{backup}`"),
            ),
        )

    if name == "checkpoints":
        recent_activity.append(_recent_line("listed checkpoints"))
        return _complete("listed restore points", _checkpoints_shell_renderable())

    if name == "log":
        if args and args[0].lower() == "exit":
            return _complete("log subprocess closed")
        if len(args) > 1 or (args and not args[0].isdigit()):
            return _fail("use `/log` or `/log <count>`")
        tail = int(args[0]) if args else None
        recent_activity.append(_recent_line("viewed session log"))
        return _complete("loaded session log", _session_log_renderable(".", tail=tail))

    if name == "docs":
        if args and args[0].lower() == "exit":
            return _complete("docs subprocess closed")
        if len(args) > 1:
            return _fail("use `/docs` or `/docs <topic>`")
        topic = args[0].lower() if args else None
        if topic is not None and topic not in DOC_TOPICS:
            available = ", ".join(sorted(DOC_TOPICS))
            return _fail(f"unknown docs topic `{args[0]}`", Text.from_markup(f"[dim]available  {available}[/dim]"))
        recent_activity.append(_recent_line("opened docs"))
        return _complete("loaded docs", _docs_shell_renderable(topic))

    return _fail(f"unknown slash command: /{name}")


def _screen_prompt_with_motion(prompt: str, *, target: str, agent_name: str, recent_activity: list[str]) -> tuple[list, int]:
    result: dict[str, tuple[list, int]] = {}

    def _worker() -> None:
        result["review"] = _review_prompt(prompt, target=target, render_clear=False, show_status=False)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    animate_surveillance(
        prompt,
        cwd=target,
        agent=agent_name,
        recent_activity=recent_activity,
        screening_enabled=get_enabled(),
    )
    thread.join()
    return result["review"]


def _restore_terminal_cursor() -> None:
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()


def _run_selected_agent(
    agent_path: str,
    prompt: str,
    *,
    agent_name: str,
    recent_activity: list[str],
    session_state: ShellSessionState | None = None,
) -> None:
    launch_cwd = os.getcwd()
    agent_argv = [agent_path, prompt]
    audit_requested = bool(session_state and session_state.audit_active)

    if audit_requested and _tmux_available() and not _tmux_in_session():
        try:
            result_code = _run_agent_in_ephemeral_tmux_session(agent_argv, cwd=launch_cwd)
        except (OSError, subprocess.CalledProcessError) as exc:
            _restore_terminal_cursor()
            recent_activity.append(_recent_line("tmux session failed to start"))
            fail("agent launch failed", str(exc))
            console.print()
            _shell_pause()
            return

        if result_code is not None:
            _restore_terminal_cursor()
            if result_code == 0:
                recent_activity.append(_recent_line(f"{agent_name} session returned"))
                return

            recent_activity.append(_recent_line(f"{agent_name} exited with code {result_code}"))
            fail(f"{agent_name} exited with code {result_code}", "see agent output above")
            console.print()
            _shell_pause()
            return

    if audit_requested and _tmux_in_session():
        pane_id = _ensure_tmux_audit_pane(session_state, cwd=launch_cwd) if session_state else None
        if pane_id:
            recent_activity.append(_recent_line("audit stream attached in the current tmux terminal"))

    try:
        result = subprocess.run(agent_argv, cwd=launch_cwd)
    except OSError as exc:
        _restore_terminal_cursor()
        recent_activity.append(_recent_line(f"{agent_name} failed to launch"))
        fail("agent launch failed", str(exc))
        console.print()
        _shell_pause()
        return

    _restore_terminal_cursor()
    if result.returncode == 0:
        recent_activity.append(_recent_line(f"{agent_name} session returned"))
        return

    recent_activity.append(_recent_line(f"{agent_name} exited with code {result.returncode}"))
    fail(f"{agent_name} exited with code {result.returncode}", "see agent output above")
    console.print()
    _shell_pause()


def _interactive_shell() -> None:
    session_state = ShellSessionState()
    recent_activity = [
        _recent_line("screening enabled by default"),
        _recent_line("try /agent to set the coding agent you are working with"),
        _recent_line("try /help for more info"),
    ]
    shell_block: _PinnedShellBlock | None = None
    status_renderable: RenderableType | None = None

    def _release_shell_block() -> None:
        nonlocal shell_block
        if shell_block is not None:
            shell_block.close()
            shell_block = None

    try:
        while True:
            if shell_block is None:
                shell_block = _PinnedShellBlock()
                shell_block.mount(_shell_home_renderable(
                    recent_activity,
                    status=status_renderable,
                    launch_target=session_state.launch_label,
                    show_prompt_lane=True,
                ))
            else:
                shell_block.update(_shell_home_renderable(
                    recent_activity,
                    status=status_renderable,
                    launch_target=session_state.launch_label,
                    show_prompt_lane=True,
                ))
            try:
                raw = _read_pinned_prompt_line(shell_block, recent_activity, session_state, status=status_renderable)
            except (EOFError, KeyboardInterrupt):
                _release_shell_block()
                console.print()
                break

            if not raw:
                continue

            if raw.startswith("/"):
                command_log = SubprocessLog()
                command_log.add(raw.split()[0], "processing request", "running")

                def _refresh_inline(renderable: RenderableType | None) -> None:
                    if shell_block is None:
                        return
                    shell_block.update(_shell_home_renderable(
                        recent_activity,
                        prompt="",
                        submitted=False,
                        status=renderable,
                        launch_target=session_state.launch_label,
                        show_prompt_lane=True,
                    ))

                _refresh_inline(_ShellSubprocessView(session_state, command_log=command_log))
                should_continue, status_renderable = _handle_shell_command(
                    raw,
                    recent_activity,
                    session_state,
                    subprocess_log=command_log,
                    refresh_status=_refresh_inline,
                )
                if not should_continue:
                    break
                continue

            agent_name = session_state.launch_target_name
            agent_path = session_state.launch_target_path
            if not agent_path:
                # Display as subprocess item instead of breaking out of UI
                error_log = SubprocessLog()
                error_log.add("prompt", f"submitted '{raw[:40]}...'" if len(raw) > 40 else f"submitted '{raw}'", "complete")
                error_log.add("launch target", "no agent configured", "failed")
                shell_block.update(_shell_home_renderable(
                    recent_activity,
                    prompt=raw,
                    submitted=True,
                    spinner="✕",
                    status=_ShellSubprocessView(session_state, command_log=error_log),
                    launch_target=session_state.launch_label,
                    show_prompt_lane=True,
                ))
                recent_activity.append(_recent_line("prompt held until a launch target is selected"))
                continue

            if get_enabled():
                findings, score = _screen_prompt_with_motion(
                    raw,
                    target=os.getcwd(),
                    agent_name=agent_name or "ai agent",
                    recent_activity=recent_activity,
                )
                if findings:
                    # Display blocked prompt as subprocess item within UI
                    from rich.table import Table

                    blocked_log = SubprocessLog()
                    blocked_log.add("prompt", f"submitted '{prompt_preview(raw, limit=40)}'", "complete")
                    blocked_log.add("shield", "screening prompt", "complete")
                    blocked_log.add("semantic scan", "comparing anchors", "complete")
                    blocked_log.add("launch target", "blocked - risky content detected", "failed")

                    # Build findings table for display
                    findings_table = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False)
                    findings_table.add_column(width=12, no_wrap=True)
                    findings_table.add_column()
                    for finding in findings:
                        color = SEVERITY_COLOR.get(finding.severity, "white")
                        icon = SEVERITY_ICON.get(finding.severity, "◆")
                        findings_table.add_row(
                            f"[{color}]{icon}  {finding.severity.lower()}[/{color}]",
                            f"[dim]{finding.description.lower()}[/dim]",
                        )

                    blocked_body = Group(
                        Text.from_markup(f"[bold {ERROR}]Prompt blocked[/bold {ERROR}]"),
                        Text.from_markup("[dim]Canary found risky content before handoff.[/dim]"),
                        Text(""),
                        Text.from_markup(f"[bold {ACCENT}]findings[/bold {ACCENT}]"),
                        findings_table,
                    )

                    shell_block.update(_shell_home_renderable(
                        recent_activity,
                        prompt=raw,
                        submitted=True,
                        spinner="✕",
                        status=_ShellSubprocessView(session_state, command_log=blocked_log, body=blocked_body),
                        launch_target=session_state.launch_label,
                        show_prompt_lane=True,
                    ))
                    recent_activity.append(_recent_line("blocked a prompt during screening"))
                    continue
                recent_activity.append(_recent_line(f"screened prompt for {agent_name}"))
            else:
                recent_activity.append(_recent_line(f"forwarded prompt to {agent_name} with screening off"))

            animate_pipeline(
                raw,
                agent=agent_name or "ai agent",
                target=os.getcwd(),
                audit_active=session_state.audit_active,
                watcher_running=session_state.watch_active,
                watch_target=session_state.watch_target,
            )
            _run_selected_agent(
                agent_path,
                raw,
                agent_name=agent_name or "ai agent",
                recent_activity=recent_activity,
                session_state=session_state,
            )
    finally:
        _release_shell_block()


@cli.command("prompt", hidden=True)
@click.argument("text")
@click.option("--strict", is_flag=True, help="block automatically without prompting.")
@click.option("--agent", default="claude", show_default=True, help="agent binary to forward the prompt to when clear.")
@click.option("--check-only", is_flag=True, help="scan only; do not forward to the agent.")
def prompt_cmd(text, strict, agent, check_only):
    """legacy one-shot prompt review path kept for compatibility."""
    hero(subtitle="prompt firewall", path=os.getcwd())
    command_bar("prompt review")
    console.print()

    findings, score = _review_prompt(text, target=os.getcwd())

    if findings:
        if strict:
            fail("blocked", "strict mode is on")
            console.print()
            raise SystemExit(1)

        try:
            confirm = input("  continue? [y/n]  ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            confirm = "n"

        console.print()
        if confirm != "y":
            fail("blocked")
            console.print()
            raise SystemExit(1)

    if check_only:
        ok("clear" if not findings else "forwarded (check-only)")
        console.print()
        return

    agent_path = shutil.which(agent)
    if not agent_path:
        fail(f"{agent} not found", "install it or add it to your PATH")
        console.print()
        raise SystemExit(127)

    ok(f"forwarded → {agent}")
    console.print()
    raise SystemExit(subprocess.run([agent_path, text]).returncode)


def _subprocess_status_panel(
    items: list[tuple[str, str, str]],
    *,
    cwd: str | None = None,
) -> None:
    """Show a subprocess-style status panel for standalone CLI commands.

    items: list of (name, detail, status) where status is "running", "complete", "failed"
    """
    from rich.align import Align
    from rich.panel import Panel
    from rich import box

    cwd = cwd or os.getcwd()
    width = shell_frame_width()

    lines: list[Text] = []
    spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    labels = {"complete": "done", "failed": "failed", "running": "running"}

    last = len(items) - 1
    for idx, (name, detail, status) in enumerate(items):
        icon = spinners[0] if status == "running" else ("✓" if status == "complete" else "✗")
        color = ACCENT if status in ("running", "complete") else ERROR

        branch = "╰─" if idx == last else "├─"
        detail_branch = "   " if idx == last else "│  "

        line = Text()
        line.append(branch, style=f"dim {TRACE}")
        line.append(" ", style=f"dim {TRACE}")
        line.append(icon, style=f"bold {color}")
        line.append(" ", style=f"dim {TRACE}")
        line.append(name, style=f"bold {WHITE}")
        line.append("  ", style=f"dim {TRACE}")
        line.append(labels.get(status, status), style=f"bold {color}")
        lines.append(line)

        if detail:
            detail_line = Text()
            detail_line.append(detail_branch, style=f"dim {TRACE}")
            detail_line.append(" ", style=f"dim {TRACE}")
            detail_line.append(detail, style=f"dim {MUTED}")
            lines.append(detail_line)

    # Header with logo and version
    logo_text = Text.from_markup(f"""\
[bold {BRAND}]  ███████[/bold {BRAND}]
[bold {BRAND}] ███   ███  ▄▀▄ █▌█ ▄▀▄ █▀▄ █ █[/bold {BRAND}]
[bold {BRAND}] ██         █▄█ █▐█ █▄█ █▀▄ ▐█▌[/bold {BRAND}]
[bold {BRAND}] ███   ███  ▀ ▀ █ █ ▀ ▀ █ █  █[/bold {BRAND}]
[bold {BRAND}]  ███████[/bold {BRAND}]""")

    info = Group(
        Text.from_markup(f"[bold {WHITE}]canary[/bold {WHITE}]  [dim {MUTED}]v{__version__}[/dim {MUTED}]"),
        Text(""),
        Text(cwd, style=f"dim {MUTED}"),
    )

    header_layout = Table.grid(expand=False, padding=(0, 3))
    header_layout.add_column(no_wrap=True)
    header_layout.add_column()
    header_layout.add_row(logo_text, info)

    header = Panel(
        header_layout,
        border_style=BRAND,
        style=f"{WHITE} on #171717",
        box=box.HEAVY_EDGE,
        padding=(1, 2),
    )

    # Status panel
    status_panel = Panel(
        Group(*lines),
        border_style=MUTED,
        style=f"{WHITE} on #171717",
        box=box.ROUNDED,
        padding=(0, 2),
    )

    console.clear()
    console.print(header)
    console.print()
    console.print(status_panel)
    console.print()


@cli.command("on")
def on_cmd():
    """enable prompt screening."""
    set_enabled(True)
    _subprocess_status_panel([
        ("screening", "prompt firewall armed", "complete"),
    ])
    console.print(Text("  new prompts are screened before any guarded handoff", style=f"dim {MUTED}"))
    console.print()


@cli.command("off")
def off_cmd():
    """disable prompt screening (prompts pass through unchecked)."""
    set_enabled(False)
    _subprocess_status_panel([
        ("screening", "prompt firewall paused", "failed"),
    ])
    console.print(Text("  new prompts now pass straight through until you run canary on", style=f"dim {MUTED}"))
    console.print(Text("  use the protected shell or guarded shims when you want screening back on", style=f"dim {MUTED}"))
    console.print()


_WATCH_LOG_PATH = Path.home() / ".canary" / "watch.log"
_WATCH_PID_PATH = Path.home() / ".canary" / "watch.pid"


def _watch_already_running() -> int | None:
    """Return PID if a background watch is still running, else None."""
    if not _WATCH_PID_PATH.exists():
        return None
    try:
        pid = int(_WATCH_PID_PATH.read_text().strip())
        os.kill(pid, 0)  # signal 0 = existence check
        return pid
    except (ValueError, OSError):
        return None


def _spawn_background_watch(target: str, *, idle: int, continuous: bool) -> subprocess.Popen:
    canary_bin = sys.argv[0]
    cmd = [canary_bin, "watch", os.path.abspath(target), "--idle", str(idle), "--_bg"]
    if continuous:
        cmd.append("--continuous")

    _WATCH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_WATCH_LOG_PATH, "w") as log_file:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
            close_fds=True,
        )
    _WATCH_PID_PATH.write_text(str(proc.pid))
    return proc


def _spawn_background_audit(*, parent_pid: int | None = None) -> subprocess.Popen:
    """Spawn a background audit process listening for events."""
    canary_bin = sys.argv[0]
    cmd = [canary_bin, "audit", "--_bg", "--dashboard"]
    if parent_pid is not None:
        cmd.extend(["--parent-pid", str(parent_pid)])

    _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _AUDIT_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_AUDIT_LOG_PATH, "w") as log_file:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
            close_fds=True,
        )
    _AUDIT_PID_PATH.write_text(str(proc.pid))
    return proc


def _resolve_watch_agent() -> tuple[str | None, str | None]:
    return _resolve_primary_agent()


def _collect_watch_prompt(target: str, preset: str | None, *, agent_name: str) -> str | None:
    prompt_text = preset.strip() if preset else None
    interactive = preset is None

    while True:
        if interactive:
            prompt_prefix = protected_prompt_panel(
                target,
                audit_active=False,
                watcher_running=_watch_already_running() is not None,
                watch_target=os.path.abspath(target) if _watch_already_running() is not None else None,
                launch_target=agent_name,
            )
            try:
                prompt_text = _read_prompt_line(prompt_prefix)
            except (EOFError, KeyboardInterrupt):
                console.print()
                return None

        if not prompt_text:
            fail("prompt required", "enter a task for your AI agent or press Ctrl+C to cancel")
            console.print()
            if not interactive:
                return None
            prompt_text = None
            continue

        findings, _ = _review_prompt(prompt_text, target=target, render_clear=False)
        if not findings:
            return prompt_text

        fail("blocked", "edit the prompt and try again")
        console.print()
        if not interactive:
            return None
        prompt_text = None


def _launch_watch_session(target: str, *, idle: int, continuous: bool, prompt: str | None, check_only: bool) -> None:
    target = os.path.abspath(target)
    agent_name, agent_path = _resolve_watch_agent()
    if not agent_path and not check_only:
        fail("launch target unavailable", "install `claude` or `codex` and add it to your PATH")
        console.print()
        raise SystemExit(127)

    prompt_text = _collect_watch_prompt(target, prompt, agent_name=agent_name or "ai agent")
    if not prompt_text:
        note("watch cancelled")
        console.print()
        raise SystemExit(1)

    if check_only:
        show_watch_panel(
            target,
            heading="Prompt accepted",
            subheading="The prompt cleared Canary's screen and is ready to hand off into the launch target.",
            prompt=prompt_text,
            footer="check-only mode  ·  no watcher or agent process was started",
            active_step="shield",
            launch_target=agent_name or "ai agent",
        )
        return

    existing = _watch_already_running()
    if not existing:
        _spawn_background_watch(target, idle=idle, continuous=continuous)

    animate_pipeline(
        prompt_text,
        agent=agent_name or "ai agent",
        target=target,
        watcher_running=True,
        watch_target=target,
    )
    agent_argv = [agent_path, prompt_text]
    raise SystemExit(subprocess.run(agent_argv, cwd=target).returncode)


@cli.command("watch")
@click.argument("target", default=".", type=click.Path(exists=True))
@click.option("--idle", default=30, show_default=True,
              help="exit after this many seconds with no file activity.")
@click.option("--continuous", is_flag=True, help="run indefinitely, overrides --idle.")
@click.option("--prompt", default=None, help="screen and launch this prompt without opening the input panel.")
@click.option("--check-only", is_flag=True, help="screen the prompt but do not launch the agent.")
@click.option("--background", is_flag=True, help="start only the background watcher instead of the protected launcher.")
@click.option("--stop", is_flag=True, help="stop a running background watcher.")
@click.option("--log", is_flag=True, help="tail the watch log from the last session.")
@click.option("--_bg", is_flag=True, hidden=True)
def watch_cmd(target, idle, continuous, prompt, check_only, background, stop, log, _bg):
    """launch through a protected prompt surface or run the background watcher."""

    if stop:
        pid = _watch_already_running()
        if pid:
            os.kill(pid, 15)  # SIGTERM
            _WATCH_PID_PATH.unlink(missing_ok=True)
            ok("watcher stopped", f"pid {pid}")
        else:
            note("no background watcher is running")
        console.print()
        return

    if log:
        if not _WATCH_LOG_PATH.exists():
            note("no watch log found — run canary watch first")
            console.print()
            return
        try:
            subprocess.run(["tail", "-f", str(_WATCH_LOG_PATH)])
        except KeyboardInterrupt:
            pass
        return

    if _bg:
        # Internal: actually run the watcher (called by the background spawn)
        timeout = 0 if continuous else idle
        start_watch(os.path.abspath(target), idle_timeout=timeout)
        _WATCH_PID_PATH.unlink(missing_ok=True)
        return

    if not background:
        _launch_watch_session(target, idle=idle, continuous=continuous, prompt=prompt, check_only=check_only)
        return

    # Check if one is already running
    existing = _watch_already_running()
    hero(subtitle="background watcher", path=os.path.abspath(target))
    command_bar("watch")
    console.print()
    if existing:
        note(f"watcher already running  ·  pid {existing}")
        note(f"canary watch --log  ·  follow output")
        note(f"canary watch --stop  ·  stop it")
        console.print()
        return

    proc = _spawn_background_watch(os.path.abspath(target), idle=idle, continuous=continuous)

    idle_detail = "runs indefinitely" if continuous else f"exits after {idle}s idle"
    result_panel(
        Group(
            live_activity_text("watching", int(time.time() * 6)),
            Text(f"{'─' * 36}", style=f"dim {TRACE}"),
            Text(f"  │  pid    {proc.pid}", style=f"dim {MUTED}"),
            Text(f"  │  log    {_WATCH_LOG_PATH}", style=f"dim {MUTED}"),
            Text(f"  │  mode   {idle_detail}", style=f"dim {MUTED}"),
            Text(f"{'─' * 36}", style=f"dim {TRACE}"),
            Text("  ╰─  canary watch --log   ·  follow output", style=f"dim {MUTED}"),
            Text("  ╰─  canary watch --stop  ·  stop the watcher", style=f"dim {MUTED}"),
        )
    )


@cli.command("checkpoint")
@click.argument("target", default=".", type=click.Path(exists=True))
@click.option("--name", "-n", default=None, help="give the checkpoint a name.")
@click.option("--delete", "-d", default=None, metavar="ID", help="delete a checkpoint by id or name.")
@click.option("--delete-all", is_flag=True, help="delete all checkpoints.")
def checkpoint_cmd(target, name, delete, delete_all):
    """save a named checkpoint, or delete one / all."""
    hero(subtitle="workspace snapshot", path=os.path.abspath(target))
    command_bar("checkpoint")
    console.print()

    if delete_all:
        n = delete_all_checkpoints(target)
        if n:
            ok(f"{n} checkpoint(s) deleted")
        else:
            note("no checkpoints to delete")
        console.print()
        return

    if delete:
        removed = delete_checkpoint(target, delete)
        if removed:
            ok("checkpoint deleted", delete)
        else:
            fail("not found", delete)
        console.print()
        return

    if not name:
        fail("checkpoint name required", "use `canary checkpoint --name <name>`")
        console.print()
        raise SystemExit(2)

    with console.status("[dim]saving snapshot...[/dim]", spinner="dots"):
        try:
            checkpoint_id = take_snapshot(target, name)
        except RuntimeError as exc:
            fail("checkpoint not saved", str(exc))
            console.print()
            raise SystemExit(1)

    ok("checkpoint saved", checkpoint_id)
    console.print()


@cli.command("rollback")
@click.argument("target", default=".", type=click.Path(exists=True))
@click.argument("checkpoint_id", required=False)
def rollback_cmd(target, checkpoint_id):
    """roll back all changes to the last (or specified) checkpoint."""
    checkpoints = list_checkpoints(target)
    if not checkpoints:
        hero(subtitle="restore workspace state", path=os.path.abspath(target))
        command_bar("rollback")
        console.print()
        fail("no checkpoints found", "run canary watch first")
        console.print()
        raise SystemExit(1)

    checkpoint = next((c for c in checkpoints if c["id"] == checkpoint_id), None) if checkpoint_id else checkpoints[-1]
    if checkpoint is None:
        hero(subtitle="restore workspace state", path=os.path.abspath(target))
        command_bar("rollback")
        console.print()
        fail("checkpoint not found", checkpoint_id or "")
        console.print()
        raise SystemExit(1)

    saved = datetime.datetime.fromtimestamp(checkpoint["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
    hero(subtitle="restore workspace state", path=os.path.abspath(target))
    command_bar("rollback")
    console.print()
    fields([
        ("snapshot", checkpoint["id"]),
        ("saved", saved),
    ])

    with console.status("[dim]restoring files...[/dim]", spinner="dots"):
        restored, backup = do_rollback(target, checkpoint_id)

    ok("restore complete", restored)
    note(f"backup saved as {backup}")
    console.print()


@cli.command("log")
@click.option("--json", "output_json", is_flag=True, help="output as json.")
@click.option("--tail", type=int, default=None, help="show only the last n events.")
@click.argument("target", default=".", type=click.Path(exists=True))
def log_cmd(output_json, tail, target):
    """show the full session event log."""
    events = read_log(target)
    if tail:
        events = events[-tail:]

    if output_json:
        print(_json.dumps(events, indent=2))
        return

    scope = f"last {tail}" if tail else "full"
    hero(subtitle="session timeline", path=os.path.abspath(target))
    command_bar("log")
    console.print()
    fields([("scope", scope)])

    if not events:
        note("no events yet")
        console.print()
        return

    table = Table(
        show_header=True,
        header_style="dim",
        box=None,
        padding=(0, 2),
        pad_edge=False,
    )
    table.add_column("time", style="dim", width=10, no_wrap=True)
    table.add_column("event", width=16, no_wrap=True)
    table.add_column("file", width=32, no_wrap=True)
    table.add_column("detail", style="dim")

    for event in events:
        timestamp = datetime.datetime.fromtimestamp(event["timestamp"]).strftime("%H:%M:%S")
        event_type = event["type"]
        color = EVENT_COLORS.get(event_type, "white")
        label = EVENT_LABELS.get(event_type, event_type.replace("_", " "))
        rest = {k: v for k, v in event.items() if k not in ("timestamp", "type")}

        file_col = rest.get("file", "")
        detail_parts = []
        if "drift" in rest:
            detail_parts.append(f"drift {rest['drift']:.4f}")
        if "threshold" in rest:
            detail_parts.append(f"thr {rest['threshold']}")
        if "count" in rest:
            detail_parts.append(f"{rest['count']} files")
        if "score" in rest:
            detail_parts.append(f"score {rest['score']}")
        if "finding_count" in rest:
            detail_parts.append(f"{rest['finding_count']} findings")
        if "event" in rest:
            detail_parts.append(rest["event"])
        if not detail_parts and not file_col:
            detail_parts = [_json.dumps(rest)] if rest else []

        table.add_row(
            timestamp,
            f"[{color}]{label}[/{color}]",
            f"[dim]{file_col}[/dim]",
            "  ·  ".join(detail_parts),
        )

    result_panel(table, padding=(1, 2))
    note(f"{len(events)} event(s)")
    console.print()


@cli.command("checkpoints")
@click.argument("target", default=".", type=click.Path(exists=True))
def checkpoints_cmd(target):
    """list all saved checkpoints."""
    checkpoints = list_checkpoints(target)
    hero(subtitle="saved snapshots", path=os.path.abspath(target))
    command_bar("checkpoints")
    console.print()

    if not checkpoints:
        note("no snapshots yet")
        console.print()
        return

    table = Table(
        show_header=True,
        header_style="dim",
        box=None,
        padding=(0, 2),
        pad_edge=False,
    )
    table.add_column("#", style="dim", width=4, no_wrap=True)
    table.add_column("type", width=8, no_wrap=True)
    table.add_column("id", width=36, no_wrap=True)
    table.add_column("saved", style="dim")

    for index, checkpoint in enumerate(checkpoints, 1):
        saved = datetime.datetime.fromtimestamp(checkpoint["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        cid = checkpoint["id"]
        if cid.startswith("rollback_backup"):
            kind, color, icon = "backup", "dim", "◆"
        elif cid.startswith("checkpoint_"):
            kind, color, icon = "auto", "dim", "◆"
        else:
            kind, color, icon = "named", BRAND, "✦"
        table.add_row(
            str(index),
            f"[{color}]{icon}  {kind}[/{color}]",
            f"[{color}]{cid}[/{color}]",
            saved,
        )

    result_panel(table, padding=(1, 2))
    note(f"{len(checkpoints)} snapshot(s)  ·  canary rollback [id]  ·  canary checkpoint --delete [id]")
    console.print()


@cli.command("setup")
@click.option("--prefer", type=click.Choice(["auto", "local"], case_sensitive=False), default="auto")
@click.option("--guards", type=click.Choice(["auto", "yes", "no"], case_sensitive=False), default="auto")
def setup_cmd(prefer, guards):
    """guided setup for local IBM Granite and optional agent guardrails."""
    created_env = _write_env_if_missing()
    profile = detect_device_profile()
    chosen = _auto_setup_backend(prefer)

    hero(subtitle="guided setup", path=os.getcwd())
    command_bar("setup")
    console.print()
    fields([
        ("device", profile.summary),
        ("runtime", chosen),
    ])

    if created_env:
        ok("created .env", str(_env_path()))
        console.print()

    if not _enable_local_mode(
        allow_slow=(prefer == "local"),
        install_if_missing=True,
        download_if_missing=True,
    ):
        fail("local setup incomplete", "finish local Granite install before launching guarded sessions")
        console.print()

    shim_dir = default_shim_dir()
    found_agents = [agent for agent in ("claude", "codex") if resolve_real_binary(agent)]
    if guards != "no" and found_agents:
        install_now = guards == "yes" or _confirm("install protected agent shims now?")
        if install_now:
            for agent in found_agents:
                record = install_guard(agent, watch=False, shim_dir=shim_dir)
                ok(f"guard installed for {agent}", record.shim_path)
            if "claude" in found_agents:
                settings = _load_claude_settings()
                if not _all_hooks_installed(settings):
                    _install_hook(settings)
                    _save_claude_settings(settings)
                    ok("claude hook bundle installed", str(_CLAUDE_SETTINGS_PATH))
            note(f'export PATH="{shim_dir}:$PATH"')
            console.print()
    elif guards != "no":
        note("no supported agent binary found in PATH during setup")
        console.print()


@cli.command("docs")
@click.argument("topic", required=False, type=click.Choice(sorted(DOC_TOPICS.keys()), case_sensitive=False))
def docs_cmd(topic):
    """show built-in documentation topics."""
    hero(subtitle="built-in docs", path=os.getcwd())
    command_bar("docs" if topic is None else f"docs {topic}")
    console.print()

    if topic is None:
        table = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False)
        table.add_column(width=12, no_wrap=True, style=f"bold {BRAND}")
        table.add_column()
        for name, info in DOC_TOPICS.items():
            table.add_row(name, info["summary"])
        console.print(table)
        console.print()
        note("use `canary docs <topic>` for details")
        console.print()
        return

    for line in DOC_TOPICS[topic]["lines"]:
        console.print(line)
    console.print()


@cli.group("guard", cls=LowerGroup)
def guard_group():
    """install or inspect protected agent shims."""


@guard_group.command("install")
@click.option("--watch", is_flag=True, help="start canary watch automatically when the shim gates a prompt.")
def guard_install_cmd(watch):
    """install direct guard shims for supported agent CLIs."""
    selected = ["claude", "codex"]
    shim_dir = default_shim_dir()

    items: list[tuple[str, str, str]] = []
    installed_agents: list[str] = []

    for agent in selected:
        try:
            record = install_guard(agent, watch=watch, shim_dir=shim_dir)
            items.append((f"{agent} guard", f"shim at {record.shim_path}", "complete"))
            installed_agents.append(agent)
        except RuntimeError as exc:
            items.append((f"{agent} guard", str(exc), "failed"))

    if "claude" in installed_agents:
        settings = _load_claude_settings()
        if not _all_hooks_installed(settings):
            _install_hook(settings)
            _save_claude_settings(settings)
            items.append(("claude hooks", "bash audit bundle installed", "complete"))

    _subprocess_status_panel(items)
    console.print(Text(f"  export PATH=\"{shim_dir}:$PATH\"", style=f"dim {MUTED}"))
    console.print()


@guard_group.command("status")
def guard_status_cmd():
    """show current direct guard install status."""
    shim_dir = default_shim_dir()
    records = guard_records()
    enabled = get_enabled()

    items: list[tuple[str, str, str]] = []

    if not records:
        items.append(("guard shims", "none installed", "failed"))
    else:
        screening_status = "armed" if enabled else "paused"
        items.append(("screening", f"prompt firewall {screening_status}", "complete" if enabled else "failed"))
        for agent, record in records.items():
            detail = f"shim at {record.shim_path}"
            if record.watch:
                detail += " (watch enabled)"
            items.append((f"{agent} guard", detail, "complete"))

    _subprocess_status_panel(items)
    console.print(Text(f"  export PATH=\"{shim_dir}:$PATH\"", style=f"dim {MUTED}"))
    console.print()


@guard_group.command("remove")
def guard_remove_cmd():
    """remove installed protected agent shims."""
    selected = list(guard_records()) or ["claude", "codex"]
    items: list[tuple[str, str, str]] = []

    for agent in selected:
        remove_guard(agent)
        items.append((f"{agent} guard", "shim removed", "complete"))

    settings = _load_claude_settings()
    if _hook_installed(settings):
        _remove_hook(settings)
        _save_claude_settings(settings)
        items.append(("claude hooks", "bash audit bundle removed", "complete"))

    _subprocess_status_panel(items)
    console.print()


@cli.command("mode", hidden=True)
@click.argument("setting", required=False, type=click.Choice(["local", "status"], case_sensitive=False))
def mode_cmd(setting):
    """legacy local-runtime status shim retained for compatibility."""
    env_path = str(_env_path())

    def stored_mode():
        values = dotenv_values(env_path)
        local = str(values.get("IBM_LOCAL", "true")).strip().lower() != "false"
        if local:
            return "local", "on-device granite  ·  no hosted fallback"
        return "local", "on-device granite  ·  no hosted fallback"

    current, detail = stored_mode()

    if setting is None or setting == "status":
        profile = detect_device_profile()
        hero(subtitle="local runtime", path=os.getcwd())
        command_bar("mode")
        console.print()
        lines = [
            f"[dim]current[/dim]  [{BRAND}]{current}[/{BRAND}]",
            f"[dim]runtime[/dim]  [dim]{detail}[/dim]",
            f"[dim]device[/dim]   [dim]{profile.summary}[/dim]",
        ]
        if profile.local_warning:
            lines += ["", f"[yellow]⚠  local mode may run slower on this device[/yellow]"]
        result_panel("\n".join(lines))
        return

    hero(subtitle="local runtime", path=os.getcwd())
    command_bar("mode local")
    console.print()
    _enable_local_mode(
        allow_slow=False,
        install_if_missing=True,
        download_if_missing=True,
    )


@cli.command("usage")
def usage_cmd():
    """show local runtime readiness kept for compatibility."""
    hero(subtitle="local runtime", path=os.getcwd())
    command_bar("usage")
    console.print()
    profile = detect_device_profile()
    deps = missing_local_dependencies()
    lines = [
        f"[dim]runtime[/dim]   [{BRAND}]local only[/{BRAND}]",
        f"[dim]device[/dim]    [dim]{profile.summary}[/dim]",
        f"[dim]deps[/dim]      [white]{'ready' if not deps else ', '.join(deps)}[/white]",
        f"[dim]model[/dim]     [white]{'cached' if local_model_cached() else 'not cached'}[/white]",
    ]
    if profile.local_warning:
        lines += ["", f"[yellow]⚠  local mode may run slower on this device[/yellow]"]
    result_panel("\n".join(lines))


_RISK_COLORS = {
    "SAFE":     BRAND,
    "LOW":      BRAND,
    "MEDIUM":   "yellow",
    "HIGH":     "red",
    "CRITICAL": "bold red",
}

_RISK_ICONS = {
    "SAFE":     "●",
    "LOW":      "◆",
    "MEDIUM":   "▲",
    "HIGH":     "■",
    "CRITICAL": "✕",
}




def _render_audit_event(event: dict) -> None:
    ts = datetime.datetime.fromtimestamp(event.get("timestamp", time.time())).strftime("%H:%M:%S")
    risk = event.get("risk", "UNKNOWN")
    color = _RISK_COLORS.get(risk, "white")
    icon = _RISK_ICONS.get(risk, "◆")
    category = event.get("category", "")
    tool = event.get("tool", "")
    hook = event.get("hook", "pre")
    hook_label = "output" if hook == "post" else "tool"
    via = event.get("via", "pattern")
    stage = event.get("stage", "")

    console.print(
        f"  [dim]{ts}[/dim]  [{color}]{icon}  {risk}[/{color}]"
        f"  [dim]{category}  ·  {tool} {hook_label}"
        f"{f'  ·  {stage}' if stage else ''}  ·  {via}[/dim]"
    )
    for key in ("command", "file", "what", "repercussions", "found", "note"):
        val = event.get(key)
        if val:
            console.print(f"  [dim]   ╰─ {key:<11}[/dim]  {val}")
    console.print()


def _track_transcript(tails: dict[str, dict], transcript_path: str | None) -> None:
    if not transcript_path:
        return
    tails.setdefault(transcript_path, {"offset": 0, "remainder": ""})


def _discover_active_transcripts(max_age_secs: int = 600) -> dict[str, int]:
    """Scan compatible transcript dirs for recently modified session JSONL files.

    Returns {path: current_file_size} for files modified within max_age_secs.
    """
    now = time.time()
    found: dict[str, int] = {}
    for root in (CLAUDE_PROJECTS_DIR, CODEX_SESSIONS_DIR):
        if not root.exists():
            continue
        try:
            for path in root.rglob("*.jsonl"):
                try:
                    stat = path.stat()
                    if now - stat.st_mtime < max_age_secs:
                        found[str(path)] = stat.st_size
                except OSError:
                    pass
        except Exception:
            pass
    return found


def _audit_dashboard_event_key(event: dict) -> str:
    request_id = str(event.get("tool_use_id") or event.get("call_id") or "").strip()
    if request_id:
        return request_id
    session = str(event.get("session_id") or event.get("transcript_path") or event.get("cwd") or "")
    command = str(event.get("command", "")).strip()
    return f"{session}:{command}"


def _append_past_bash_request(past_requests: list[dict], event: dict, *, limit: int = 10) -> None:
    if not event.get("command"):
        return
    past_requests.insert(0, dict(event))
    del past_requests[limit:]


def _record_audit_dashboard_event(
    event: dict,
    current_requests: dict[str, dict],
    past_requests: list[dict],
) -> None:
    if event.get("tool") != "Bash":
        return

    key = _audit_dashboard_event_key(event)
    hook = event.get("hook", "")
    stage = event.get("stage", "")

    if stage == "rejected" or hook == "post":
        merged = {**current_requests.pop(key, {}), **event}
        _append_past_bash_request(past_requests, merged)
        return

    current_requests[key] = {**current_requests.get(key, {}), **event}
    ordered = sorted(
        current_requests.items(),
        key=lambda item: item[1].get("timestamp", 0),
        reverse=True,
    )
    for stale_key, stale_event in ordered[4:]:
        current_requests.pop(stale_key, None)
        _append_past_bash_request(past_requests, stale_event)


def _audit_dashboard_entry(
    event: dict,
    *,
    branch: str,
    detail_branch: str,
) -> RenderableType:
    ts = datetime.datetime.fromtimestamp(event.get("timestamp", time.time())).strftime("%H:%M:%S")
    risk = event.get("risk", "UNKNOWN")
    color = _RISK_COLORS.get(risk, "white")
    icon = _RISK_ICONS.get(risk, "◆")
    category = str(event.get("category", "")).strip()
    stage = str(event.get("stage", "")).strip()
    hook = str(event.get("hook", "")).strip()
    command = prompt_preview(str(event.get("command", "")), limit=100)
    detail = (
        event.get("note")
        or event.get("found")
        or event.get("repercussions")
        or event.get("what")
        or ""
    )
    stage_label = stage or ("pending approval" if hook == "permission" else "")
    stage_color = BRAND
    if stage_label in {"failed", "error", "rejected"}:
        stage_color = ERROR
    elif stage_label in {"completed", "complete"}:
        stage_color = ACCENT

    header = Text()
    header.append(branch, style=f"dim {TRACE}")
    header.append(" ", style=f"dim {TRACE}")
    header.append(icon, style=f"bold {color}")
    header.append(" ", style=f"dim {TRACE}")
    header.append(command or "bash request", style=f"bold {WHITE}")
    if stage_label:
        header.append("  ", style=f"dim {TRACE}")
        header.append(stage_label, style=f"bold {stage_color}")
    header.append("  ", style=f"dim {TRACE}")
    header.append(ts, style=f"dim {MUTED}")

    meta_bits = [bit for bit in (category, hook if hook and hook != "permission" else "") if bit]
    rows: list[RenderableType] = [header]
    meta = Text()
    meta.append(detail_branch, style=f"dim {TRACE}")
    meta.append(" ", style=f"dim {TRACE}")
    meta.append(risk, style=f"bold {color}")
    if meta_bits:
        meta.append("  ·  ", style=f"dim {TRACE}")
        meta.append(" · ".join(meta_bits), style=f"dim {WHITE}")
    rows.append(meta)
    if detail:
        detail_line = Text()
        detail_line.append(detail_branch, style=f"dim {TRACE}")
        detail_line.append(" ", style=f"dim {TRACE}")
        detail_line.append(prompt_preview(str(detail), limit=112), style=f"dim {WHITE}")
        rows.append(detail_line)
    return Group(*rows)


def _audit_dashboard_column(
    title: str,
    entries: list[dict],
    *,
    empty_text: str,
) -> RenderableType:
    body: list[RenderableType] = []
    body.append(Text(title, style=f"bold {BRAND}"))
    body.append(Rule(style=BRAND))
    if entries:
        for idx, entry in enumerate(entries):
            branch = "╰─" if idx == len(entries) - 1 else "├─"
            detail_branch = "   " if idx == len(entries) - 1 else "│  "
            body.append(_audit_dashboard_entry(entry, branch=branch, detail_branch=detail_branch))
    else:
        body.append(Text.from_markup(f"[dim]{empty_text}[/dim]"))
    return Group(*body)


def _audit_dashboard_renderable(
    current_requests: dict[str, dict],
    past_requests: list[dict],
    *,
    last_event_time: float,
    frame: int = 0,
) -> RenderableType:
    current_entries = sorted(
        current_requests.values(),
        key=lambda entry: entry.get("timestamp", 0),
        reverse=True,
    )
    current_panel = _audit_dashboard_column(
        "current requests",
        current_entries,
        empty_text="Waiting for live Bash requests.",
    )
    past_panel = _audit_dashboard_column(
        "past requests",
        past_requests[:6],
        empty_text="No completed or rejected Bash requests yet.",
    )

    summary = live_activity_text("auditing", frame)
    summary.stylize("bold")
    counts = Text()
    counts.append(f"{len(current_entries)} open", style=f"bold {BRAND}")
    counts.append("  ·  ", style=f"dim {TRACE}")
    counts.append(f"{len(past_requests)} reviewed", style=f"bold {WHITE}")
    counts.append("  ·  ", style=f"dim {TRACE}")
    counts.append("Ctrl-C to stop", style=f"dim {MUTED}")

    activity = Text.from_markup(f"[dim]last activity  {int(max(0, time.time() - last_event_time))}s ago[/dim]")
    width = shell_frame_width()
    if width >= 110:
        columns = Table.grid(expand=True, padding=(0, 3))
        columns.add_column(ratio=7)
        columns.add_column(ratio=5)
        columns.add_row(current_panel, past_panel)
        body = Group(summary, counts, activity, Rule(style=TRACE), columns)
    else:
        body = Group(summary, counts, activity, Rule(style=TRACE), current_panel, Text(""), past_panel)

    return Group(
        Text(""),
        body,
        Text(""),
    )


def _audit_listen(*, dashboard: bool = False, parent_pid: int | None = None) -> None:
    from .bash_auditor import audit_command

    current_requests: dict[str, dict] = {}
    past_requests: list[dict] = []

    if dashboard:
        console.clear()
    else:
        hero(subtitle="audit stream", path=os.getcwd())
        command_bar("audit")
        console.print()

        note("waiting for AI agent tool activity  ·  Ctrl-C to stop")
        note("reading Canary hook events plus compatible Claude and Codex transcript hints")
        console.print()

    audit_offset = _AUDIT_EVENTS_PATH.stat().st_size if _AUDIT_EVENTS_PATH.exists() else 0
    audit_remainder = ""
    transcript_tails: dict[str, dict] = {}
    transcript_commands: dict[str, dict] = {}
    seen_intents: set[str] = set()
    seen_results: set[tuple[str, str]] = set()
    last_event_time = time.time()
    event_count = 0
    last_scan_time = 0.0
    _TRANSCRIPT_SCAN_INTERVAL = 5.0
    frame = 0
    parent_exited = False

    # Seed from any already-active compatible transcript sessions.
    for tpath, fsize in _discover_active_transcripts().items():
        # Start 4 KB back so we catch in-flight pending commands
        transcript_tails[tpath] = {"offset": max(0, fsize - 4096), "remainder": ""}

    def _emit(event: dict) -> None:
        if dashboard:
            _record_audit_dashboard_event(event, current_requests, past_requests)
            return
        _render_audit_event(event)

    try:
        with Live(
            _audit_dashboard_renderable(
                current_requests,
                past_requests,
                last_event_time=last_event_time,
                frame=frame,
            ),
            console=console,
            refresh_per_second=12,
            transient=False,
        ) if dashboard else nullcontext() as live:
            while True:
                time.sleep(0.12)
                frame += 1
                saw_activity = False
                now = time.time()

                if parent_pid is not None:
                    try:
                        os.kill(parent_pid, 0)
                    except OSError:
                        parent_exited = True
                        break

                # Periodically re-scan for new compatible transcript sessions.
                if now - last_scan_time >= _TRANSCRIPT_SCAN_INTERVAL:
                    for tpath, fsize in _discover_active_transcripts().items():
                        if tpath not in transcript_tails:
                            transcript_tails[tpath] = {"offset": fsize, "remainder": ""}
                    last_scan_time = now

                audit_offset, audit_remainder, audit_entries = read_jsonl_since(
                    _AUDIT_EVENTS_PATH, audit_offset, audit_remainder
                )
                for event in audit_entries:
                    if not isinstance(event, dict):
                        continue
                    _track_transcript(transcript_tails, event.get("transcript_path"))
                    _emit(event)
                    saw_activity = True
                    event_count += 1

                for transcript_path, tail in list(transcript_tails.items()):
                    offset, remainder, entries = read_jsonl_since(
                        transcript_path,
                        tail["offset"],
                        tail["remainder"],
                    )
                    tail["offset"] = offset
                    tail["remainder"] = remainder

                    for entry in entries:
                        for intent in iter_bash_tool_uses(entry):
                            tool_use_id = intent.get("tool_use_id") or (
                                f"{transcript_path}:{intent.get('timestamp')}:{intent['command']}"
                            )
                            if tool_use_id in seen_intents:
                                transcript_commands.setdefault(tool_use_id, intent)
                                continue

                            result = audit_command(intent["command"])
                            via = "granite" if result.via_llm else "pattern"
                            enriched = {
                                **intent,
                                "risk": result.risk,
                                "category": result.category,
                                "via": via,
                                "what": result.what,
                                "repercussions": result.repercussions,
                            }
                            transcript_commands[tool_use_id] = enriched
                            seen_intents.add(tool_use_id)
                            _emit({
                                "tool_use_id": tool_use_id,
                                "timestamp": intent.get("timestamp") or time.time(),
                                "tool": "Bash",
                                "risk": result.risk,
                                "category": result.category,
                                "via": via,
                                "command": intent["command"][:120],
                                "what": result.what,
                                "repercussions": result.repercussions,
                                "hook": "permission" if intent.get("session_id") else "",
                                "stage": "pending approval" if intent.get("session_id") else "requested",
                            })
                            saw_activity = True
                            event_count += 1

                        for result in iter_tool_results(entry):
                            tool_use_id = result.get("tool_use_id", "")
                            result_state = str(result.get("state") or tool_result_state(result.get("content", ""))).lower()
                            result_key = (tool_use_id, result_state)
                            if not tool_use_id or result_key in seen_results:
                                continue

                            prior = transcript_commands.get(tool_use_id)
                            if prior is None:
                                continue

                            if result_state == "rejected":
                                seen_results.add(result_key)
                                _emit({
                                    "tool_use_id": tool_use_id,
                                    "timestamp": result.get("timestamp") or time.time(),
                                    "tool": "Bash",
                                    "risk": prior.get("risk", "HIGH"),
                                    "category": "permission",
                                    "via": "transcript",
                                    "command": prior.get("command", "")[:120],
                                    "note": "the pending Bash command was rejected before execution",
                                    "hook": "permission",
                                    "stage": "rejected",
                                })
                                saw_activity = True
                                event_count += 1
                                continue

                            if result_state in {"completed", "failed", "error"}:
                                seen_results.add(result_key)
                                exit_code = result.get("exit_code")
                                completion_event = {
                                    "tool_use_id": tool_use_id,
                                    "timestamp": result.get("timestamp") or time.time(),
                                    "tool": "Bash",
                                    "risk": prior.get("risk", "HIGH"),
                                    "category": prior.get("category", ""),
                                    "via": prior.get("via", "transcript"),
                                    "command": prior.get("command", "")[:120],
                                    "what": prior.get("what", ""),
                                    "repercussions": prior.get("repercussions", ""),
                                    "hook": "post",
                                    "stage": "completed" if result_state == "completed" else result_state,
                                }
                                if isinstance(exit_code, int) and exit_code != 0:
                                    completion_event["note"] = f"command exited with code {exit_code}"
                                _emit(completion_event)
                                saw_activity = True
                                event_count += 1

                if saw_activity:
                    last_event_time = time.time()

                if dashboard and live is not None:
                    live.update(_audit_dashboard_renderable(
                        current_requests,
                        past_requests,
                        last_event_time=last_event_time,
                        frame=frame,
                    ))
    except KeyboardInterrupt:
        pass

    if parent_exited:
        return

    if dashboard:
        console.clear()
        console.print(_audit_dashboard_renderable(
            current_requests,
            past_requests,
            last_event_time=last_event_time,
            frame=frame,
        ))
        console.print(f"  [dim]session ended  ·  {event_count} audit event(s)[/dim]")
        console.print()
        return

    note(f"session ended  ·  {event_count} audit event(s)")
    console.print()


_AUDIT_LOG_PATH = Path.home() / ".canary" / "audit.log"
_AUDIT_PID_PATH = Path.home() / ".canary" / "audit.pid"


def _audit_already_running() -> int | None:
    if not _AUDIT_PID_PATH.exists():
        return None
    try:
        pid = int(_AUDIT_PID_PATH.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, OSError):
        return None


@cli.command("audit")
@click.option("--idle", default=None, hidden=True)
@click.option("--stop", is_flag=True, help="stop a running background auditor.")
@click.option("--log", is_flag=True, help="tail the audit log from the last session.")
@click.option("--inline", "_inline", is_flag=True, hidden=True)
@click.option("--dashboard", is_flag=True, hidden=True)
@click.option("--_bg", is_flag=True, hidden=True)
@click.option("--parent-pid", default=None, type=int, hidden=True)
def audit_cmd(idle, stop, log, _inline, dashboard, _bg, parent_pid):
    """open a live audit stream for the next agent session."""
    del idle

    if stop:
        pid = _audit_already_running()
        if pid:
            os.kill(pid, 15)
            _AUDIT_PID_PATH.unlink(missing_ok=True)
            ok("auditor stopped", f"pid {pid}")
        else:
            note("no background auditor is running")
        console.print()
        return

    if log:
        if not _AUDIT_LOG_PATH.exists():
            note("no audit log found — run canary audit first")
            console.print()
            return
        try:
            subprocess.run(["tail", "-f", str(_AUDIT_LOG_PATH)])
        except KeyboardInterrupt:
            pass
        return

    if _bg or _inline:
        _audit_listen(dashboard=dashboard, parent_pid=parent_pid)
        _AUDIT_PID_PATH.unlink(missing_ok=True)
        return

    _audit_listen(dashboard=dashboard)


@cli.command("perms")
def perms_cmd():
    """show always-allowed Bash permissions from claude settings."""
    hero(subtitle="claude permissions", path=str(_CLAUDE_SETTINGS_PATH))
    command_bar("perms")
    console.print()
    permissions_renderable, _ = _bash_permissions_renderable()
    result_panel(permissions_renderable)


def _hook_stderr_line(tag: str, level: str, category: str, via: str, fields: list[tuple[str, str]]) -> None:
    """Write a compact hook analysis line to stderr."""
    err = Console(stderr=True)
    color = _RISK_COLORS.get(level, "white")
    icon = _RISK_ICONS.get(level, "◆")
    err.print(f"\n  [bold {color}]{icon}[/bold {color}]  [bold]{tag}[/bold]  [{color}]{level}[/{color}]  [dim]{category}  ·  {via}[/dim]")
    for label, value in fields:
        err.print(f"  [dim]   ╰─ {label:<11}[/dim]  {value}")
    err.print()


@cli.command("audit-hook", hidden=True)
def audit_hook_cmd():
    """Claude Code hook: analyze pending tool use and permission requests."""
    from .bash_auditor import audit_command
    from .prompt_firewall import scan_prompt
    from .risk import compute_risk_score
    from .sensitive_files import is_sensitive

    try:
        data = _json.loads(sys.stdin.read())
        hook_event_name = data.get("hook_event_name", "PreToolUse")
        tool_name = data.get("tool_name", "")
        inp = data.get("tool_input", {})
    except Exception:
        sys.exit(0)

    meta = {
        "hook_event_name": hook_event_name,
        "session_id": data.get("session_id", ""),
        "transcript_path": data.get("transcript_path", ""),
        "cwd": data.get("cwd", ""),
    }

    try:
        if tool_name == "Bash":
            command = inp.get("command", "").strip()
            if not command:
                sys.exit(0)
            result = audit_command(command)
            via = "granite" if result.via_llm else "pattern"
            hook = "permission" if hook_event_name == "PermissionRequest" else "pre"
            _hook_stderr_line(
                "canary audit", result.risk, result.category,
                via,
                [("what", result.what), ("repercussions", result.repercussions)],
            )
            _append_audit_event({
                "tool": "Bash", "risk": result.risk,
                "category": result.category, "via": via,
                "hook": hook,
                "command": command[:120],
                "what": result.what, "repercussions": result.repercussions,
                **meta,
            })

        elif tool_name in ("Write", "Edit"):
            file_path = inp.get("file_path", "")
            content = inp.get("content") or inp.get("new_string") or ""

            if is_sensitive(file_path):
                _hook_stderr_line(
                    "canary audit", "HIGH", "sensitive-write", "pattern",
                    [("file", file_path), ("note", "writing to a sensitive file path")],
                )
                _append_audit_event({
                    "tool": tool_name, "risk": "HIGH",
                    "category": "sensitive-write", "via": "pattern",
                    "file": file_path, "note": "writing to a sensitive file path",
                    "hook": "pre",
                    **meta,
                })
                sys.exit(0)

            if content:
                findings = scan_prompt(content[:4000])
                if findings:
                    score = compute_risk_score(findings)
                    level = "HIGH" if score > 60 else "MEDIUM"
                    descs = "  ·  ".join(f.description.lower() for f in findings[:3])
                    _hook_stderr_line(
                        "canary audit", level, "content-scan", "pattern",
                        [("file", file_path), ("found", descs)],
                    )
                    _append_audit_event({
                        "tool": tool_name, "risk": level,
                        "category": "content-scan", "via": "pattern",
                        "file": file_path, "found": descs,
                        "hook": "pre",
                        **meta,
                    })
    except Exception:
        pass

    sys.exit(0)


@cli.command("prompt-hook", hidden=True)
def prompt_hook_cmd():
    """claude code userpromptsubmit hook: screens the user's prompt before it reaches claude."""
    from .guard import get_enabled

    if not get_enabled():
        sys.exit(0)

    try:
        data = _json.loads(sys.stdin.read())
        prompt = data.get("prompt", "")
    except Exception:
        sys.exit(0)

    meta = {
        "hook_event_name": data.get("hook_event_name", "UserPromptSubmit"),
        "session_id": data.get("session_id", ""),
        "transcript_path": data.get("transcript_path", ""),
        "cwd": data.get("cwd", ""),
    }

    if not prompt:
        sys.exit(0)

    try:
        findings = scan_prompt(prompt)
        if not findings:
            sys.exit(0)

        score = compute_risk_score(findings)
        descs = "; ".join(f.description for f in findings[:5])
        level = "HIGH" if score > 60 else "MEDIUM"

        _append_audit_event({
            "tool": "UserPrompt", "risk": level,
            "category": "prompt-screen", "via": "pattern",
            "score": score, "found": descs,
            **meta,
        })

        if score >= 60:
            reason = f"canary blocked prompt — {descs}"
            print(_json.dumps({"decision": "block", "reason": reason}))
            sys.exit(2)

        # warn but allow through
        print(
            f"\n[canary] {level} risk prompt ({score}/100) — {descs}\n"
            "  Use 'canary off' to disable screening.\n",
            file=sys.stderr,
        )
    except Exception:
        pass

    sys.exit(0)


@cli.command("watch-hook", hidden=True)
def watch_hook_cmd():
    """claude code posttooluse hook: scans what the agent just did for exposure."""
    from .prompt_firewall import scan_prompt
    from .risk import compute_risk_score

    try:
        data = _json.loads(sys.stdin.read())
        tool_name = data.get("tool_name", "")
        inp = data.get("tool_input", {})
        resp = data.get("tool_response", {})
    except Exception:
        sys.exit(0)

    meta = {
        "hook_event_name": data.get("hook_event_name", "PostToolUse"),
        "session_id": data.get("session_id", ""),
        "transcript_path": data.get("transcript_path", ""),
        "cwd": data.get("cwd", ""),
    }

    try:
        if tool_name == "Bash":
            output = str(resp.get("output", "")).strip()
            if not output:
                sys.exit(0)
            findings = scan_prompt(output[:3000])
            if findings:
                score = compute_risk_score(findings)
                level = "HIGH" if score > 60 else "MEDIUM"
                command = inp.get("command", "")[:60]
                descs = "  ·  ".join(f.description.lower() for f in findings[:3])
                _hook_stderr_line(
                    "canary watch", level, "output-scan", "pattern",
                    [("command", command), ("found", descs),
                     ("note", "sensitive data appeared in command output")],
                )
                _append_audit_event({
                    "tool": "Bash", "hook": "post",
                    "risk": level, "category": "output-scan", "via": "pattern",
                    "command": command, "found": descs,
                    "note": "sensitive data appeared in command output",
                    **meta,
                })
    except Exception:
        pass

    sys.exit(0)


_CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

# (event_type, tool_matcher_or_None, hook_command)
# matcher=None means the event has no tool matcher (e.g. UserPromptSubmit)
_HOOK_SPECS: list[tuple[str, str | None, str]] = [
    ("PreToolUse",       "Bash",  "canary audit-hook"),
    ("PermissionRequest","Bash",  "canary audit-hook"),
    ("PreToolUse",       "Write", "canary audit-hook"),
    ("PreToolUse",       "Edit",  "canary audit-hook"),
    ("PostToolUse",      "Bash",  "canary watch-hook"),
    ("UserPromptSubmit", None,    "canary prompt-hook"),
]


def _load_claude_settings() -> dict:
    if _CLAUDE_SETTINGS_PATH.exists():
        try:
            return _json.loads(_CLAUDE_SETTINGS_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_claude_settings(settings: dict) -> None:
    _CLAUDE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CLAUDE_SETTINGS_PATH.write_text(_json.dumps(settings, indent=2) + "\n")


def _has_hook_entry(settings: dict, event: str, matcher: str | None, command: str) -> bool:
    event_list = settings.get("hooks", {}).get(event, [])
    entry = {"type": "command", "command": command}
    return any(
        entry in block.get("hooks", [])
        for block in event_list
        if block.get("matcher") == matcher
    )


def _hook_installed(settings: dict) -> bool:
    """True if any Canary hook entry is present."""
    return any(_has_hook_entry(settings, event, matcher, command) for event, matcher, command in _HOOK_SPECS)


def _all_hooks_installed(settings: dict) -> bool:
    """True if the full current Canary hook set is present."""
    return all(_has_hook_entry(settings, event, matcher, command) for event, matcher, command in _HOOK_SPECS)


def _install_hook(settings: dict) -> None:
    hooks = settings.setdefault("hooks", {})
    for event, matcher, command in _HOOK_SPECS:
        event_list = hooks.setdefault(event, [])
        entry = {"type": "command", "command": command}
        if matcher is None:
            # No tool matcher (e.g. UserPromptSubmit)
            if not event_list:
                event_list.append({"hooks": [entry]})
            else:
                block = event_list[0]
                if entry not in block.setdefault("hooks", []):
                    block["hooks"].append(entry)
        else:
            for block in event_list:
                if block.get("matcher") == matcher:
                    if entry not in block.setdefault("hooks", []):
                        block["hooks"].append(entry)
                    break
            else:
                event_list.append({"matcher": matcher, "hooks": [entry]})


def _remove_hook(settings: dict) -> None:
    hook_commands = {cmd for _, _, cmd in _HOOK_SPECS}
    seen_events: set[str] = set()
    for event, _, _ in _HOOK_SPECS:
        if event in seen_events:
            continue
        seen_events.add(event)
        event_list = settings.get("hooks", {}).get(event, [])
        for block in event_list:
            block["hooks"] = [
                h for h in block.get("hooks", [])
                if h.get("command") not in hook_commands
            ]
        settings["hooks"][event] = [b for b in event_list if b.get("hooks")]


@cli.group("hook", cls=LowerGroup, hidden=True)
def hook_group():
    """manage the claude code bash audit hook."""


@hook_group.command("remove")
def hook_remove_cmd():
    """remove the bash audit hook from claude code settings."""
    hero(subtitle="claude code hook", path=str(_CLAUDE_SETTINGS_PATH))
    command_bar("hook remove")
    console.print()

    settings = _load_claude_settings()
    if not _hook_installed(settings):
        note("hook is not installed")
        console.print()
        return

    _remove_hook(settings)
    _save_claude_settings(settings)
    ok("hook removed")
    console.print()


@hook_group.command("status")
def hook_status_cmd():
    """show all active canary hooks in claude code settings."""
    hero(subtitle="claude code hooks", path=str(_CLAUDE_SETTINGS_PATH))
    command_bar("hook status")
    console.print()

    settings = _load_claude_settings()
    lines = [f"[dim]settings  {_CLAUDE_SETTINGS_PATH}[/dim]", ""]

    any_installed = False
    for event, matcher, command in _HOOK_SPECS:
        event_list = settings.get("hooks", {}).get(event, [])
        entry = {"type": "command", "command": command}
        active = any(
            entry in block.get("hooks", [])
            for block in event_list
            if block.get("matcher") == matcher
        )
        mark = f"[{BRAND}]✓[/{BRAND}]" if active else "[dim]✗[/dim]"
        matcher_label = matcher or "-"
        lines.append(f"  {mark}  [dim]{event:<17}  {matcher_label:<8}  {command}[/dim]")
        if active:
            any_installed = True

    if not any_installed:
        lines += ["", "[dim]no canary hooks installed  ·  run canary guard install[/dim]"]

    result_panel("\n".join(lines))


def _show_usage_error(e: "click.UsageError") -> None:
    from rich.console import Console as _Console
    err = _Console(stderr=True)
    if e.ctx is not None:
        raw = e.ctx.get_usage()
        usage_body = raw.removeprefix("Usage: ").removeprefix("usage: ")
        err.print(f"\n  [dim]usage  {usage_body}[/dim]")
    err.print(f"  [bold red]✕[/bold red]  {e.format_message()}")
    if e.ctx is not None:
        err.print(f"  [dim]╰─  {e.ctx.command_path} --help  ·  show options[/dim]")
    err.print()


def main() -> None:
    import click as _click
    try:
        cli(standalone_mode=False)
    except _click.UsageError as e:
        _show_usage_error(e)
        sys.exit(2)
    except _click.exceptions.Exit as e:
        sys.exit(e.code)
    except _click.Abort:
        sys.exit(1)


if __name__ == "__main__":
    main()
