"""click cli entrypoint."""
import datetime
import json as _json
import os
import shutil
import subprocess
import sys
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
from rich.console import Console
from rich.table import Table

load_dotenv()

from . import __version__
from .usage import get_usage, get_limits, near_limit
from .checkpoint import delete_all_checkpoints, delete_checkpoint, list_checkpoints, rollback as do_rollback, take_snapshot
from .device import detect_device_profile
from .docs_topics import DOC_TOPICS
from .guard import DEFAULT_SHIM_DIR, get_enabled, guard_records, install_guard, remove_guard, resolve_real_binary, set_enabled
from .local_embeddings import ensure_local_model, install_local_dependencies, local_model_cached, missing_local_dependencies
from .prompt_firewall import scan_prompt
from .risk import compute_risk_score, render_findings
from .semantic_firewall import semantic_scan
from .session import log_event, read_log
from .ui import BRAND, command_bar, console, fail, fields, hero, note, ok, result_panel, warn
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

ENV_TEMPLATE = """# required for online mode. get from ibm cloud → manage → access → api keys.
IBM_API_KEY=

# required for online mode. get from watsonx.ai → projects → manage.
IBM_PROJECT_ID=

# region endpoint. one of: us-south | eu-de | jp-tok | eu-gb | au-syd
IBM_REGION=us-south

# set to `true` to run granite locally via huggingface (no ibm account needed).
# requires: pip install "canary-watch[local]"
IBM_LOCAL=false
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


def _print_home() -> None:
    hero(
        subtitle="agent watchdog  ·  prompt firewall  ·  drift detection",
        use_logo=True,
    )
    command_bar("available commands")

    table = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False)
    table.add_column(width=12, no_wrap=True, style=f"bold {BRAND}")
    table.add_column()

    state = "[bold #ccff04]on[/bold #ccff04]" if get_enabled() else "[dim]off[/dim]"
    rows = [
        ("on · off", f"toggle prompt screening  ·  currently {state}"),
        ("prompt", "review a prompt before handoff"),
        ("audit", "monitor the next agent session for risky tool calls"),
        ("watch", "watch a repo during an agent run"),
        ("checkpoint", "save a clean snapshot"),
        ("rollback", "restore from a snapshot"),
        ("log", "show the event log"),
        ("checkpoints", "list saved snapshots"),
        ("setup", "guided install and backend setup"),
        ("docs", "built-in help topics"),
        ("guard", "install direct claude code guardrails"),
        ("mode", "switch inference backend"),
        ("usage", "show daily api usage vs limits"),
    ]
    for command, summary in rows:
        table.add_row(command, summary)

    console.print(table)
    console.print()
    note("use canary <command> --help for details")
    console.print()


@click.group(cls=LowerGroup, invoke_without_command=True)
@click.version_option(__version__, prog_name="canary", help="show the version and exit.")
@click.pass_context
def cli(ctx):
    """canary — ai agent watchdog."""
    if ctx.invoked_subcommand is None:
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
            fail("staying on online")
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
    profile = detect_device_profile()
    if prefer == "local":
        return "local"
    if prefer == "online":
        return "online"
    return profile.recommended_mode


@cli.command("prompt")
@click.argument("text")
@click.option("--strict", is_flag=True, help="block automatically without prompting.")
@click.option("--agent", default="claude", show_default=True, help="agent binary to forward the prompt to when clear.")
@click.option("--check-only", is_flag=True, help="scan only; do not forward to the agent.")
def prompt_cmd(text, strict, agent, check_only):
    """scan a prompt for sensitive information, then forward to the agent if clear."""
    hero(subtitle="prompt firewall", path=os.getcwd())
    command_bar("prompt review")

    findings = scan_prompt(text)
    with console.status("[dim]reviewing...[/dim]", spinner="dots"):
        findings += semantic_scan(text)

    score = compute_risk_score(findings)
    render_findings(findings, score)

    log_event("prompt_scan", {
        "score": score,
        "finding_count": len(findings),
        "severities": [f.severity for f in findings],
    })

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


@cli.command("on")
def on_cmd():
    """enable prompt screening for all claude code calls."""
    hero(subtitle="prompt screening", path=os.getcwd())
    command_bar("on")
    set_enabled(True)
    result_panel(
        f"[bold {BRAND}]◉[/bold {BRAND}]  screening [bold white]enabled[/bold white]\n"
        f"[dim]{'─' * 34}[/dim]\n"
        f"  [dim]╰─  all prompts checked before reaching the agent[/dim]\n"
        f"  [dim]╰─  pass [white]-ignore[/white] to bypass for a single call[/dim]"
    )


@cli.command("off")
def off_cmd():
    """disable prompt screening (prompts pass through unchecked)."""
    hero(subtitle="prompt screening", path=os.getcwd())
    command_bar("off")
    set_enabled(False)
    result_panel(
        f"[bold yellow]◉[/bold yellow]  screening [bold white]disabled[/bold white]\n"
        f"[dim]{'─' * 34}[/dim]\n"
        f"  [dim]╰─  prompts pass through to the agent unchecked[/dim]\n"
        f"  [dim]╰─  pass [white]-safe[/white] to force screening for a single call[/dim]"
    )


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


@cli.command("watch")
@click.argument("target", default=".", type=click.Path(exists=True))
@click.option("--idle", default=30, show_default=True,
              help="exit after this many seconds with no file activity.")
@click.option("--continuous", is_flag=True, help="run indefinitely, overrides --idle.")
@click.option("--stop", is_flag=True, help="stop a running background watcher.")
@click.option("--log", is_flag=True, help="tail the watch log from the last session.")
@click.option("--_bg", is_flag=True, hidden=True)
def watch_cmd(target, idle, continuous, stop, log, _bg):
    """start a background watcher for the next agent session."""
    import subprocess

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

    # Check if one is already running
    existing = _watch_already_running()
    if existing:
        hero(subtitle="background watcher", path=os.path.abspath(target))
        command_bar("watch")
        note(f"watcher already running  ·  pid {existing}")
        note(f"canary watch --log  ·  follow output")
        note(f"canary watch --stop  ·  stop it")
        console.print()
        return

    # Spawn background process
    hero(subtitle="background watcher", path=os.path.abspath(target))
    command_bar("watch")

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

    idle_detail = "runs indefinitely" if continuous else f"exits after {idle}s idle"
    result_panel(
        f"[bold {BRAND}]◉[/bold {BRAND}]  watcher running in background\n"
        f"[dim]{'─' * 36}[/dim]\n"
        f"  [dim]│  pid    {proc.pid}[/dim]\n"
        f"  [dim]│  log    {_WATCH_LOG_PATH}[/dim]\n"
        f"  [dim]│  mode   {idle_detail}[/dim]\n"
        f"[dim]{'─' * 36}[/dim]\n"
        f"  [dim]╰─  canary watch --log   ·  follow output[/dim]\n"
        f"  [dim]╰─  canary watch --stop  ·  stop the watcher[/dim]"
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

    with console.status("[dim]saving snapshot...[/dim]", spinner="dots"):
        checkpoint_id = take_snapshot(target, name)

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
        fail("no checkpoints found", "run canary watch first")
        console.print()
        raise SystemExit(1)

    checkpoint = next((c for c in checkpoints if c["id"] == checkpoint_id), None) if checkpoint_id else checkpoints[-1]
    if checkpoint is None:
        hero(subtitle="restore workspace state", path=os.path.abspath(target))
        command_bar("rollback")
        fail("checkpoint not found", checkpoint_id or "")
        console.print()
        raise SystemExit(1)

    saved = datetime.datetime.fromtimestamp(checkpoint["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
    hero(subtitle="restore workspace state", path=os.path.abspath(target))
    command_bar("rollback")
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
@click.option("--prefer", type=click.Choice(["auto", "local", "online"], case_sensitive=False), default="auto")
@click.option("--guards", type=click.Choice(["auto", "yes", "no"], case_sensitive=False), default="auto")
def setup_cmd(prefer, guards):
    """guided setup for local/online backends and agent guardrails."""
    created_env = _write_env_if_missing()
    profile = detect_device_profile()
    chosen = _auto_setup_backend(prefer)

    hero(subtitle="guided setup", path=os.getcwd())
    command_bar("setup")
    fields([
        ("device", profile.summary),
        ("recommended", profile.recommended_mode),
        ("selected", chosen),
    ])

    if created_env:
        ok("created .env", str(_env_path()))
        console.print()

    if chosen == "local":
        if not _enable_local_mode(
            allow_slow=(prefer == "local"),
            install_if_missing=True,
            download_if_missing=True,
        ):
            _set_local_mode(False)
            warn("falling back to online", "local support was not enabled")
            console.print()
    else:
        _set_local_mode(False)
        ok("online mode", "managed cloud inference ready")
        if profile.local_warning:
            note("this device is better suited to online mode")
        console.print()

    found_agents = [agent for agent in ("claude",) if resolve_real_binary(agent, shim_dir=DEFAULT_SHIM_DIR)]
    if guards != "no" and found_agents:
        install_now = guards == "yes" or _confirm("install direct claude code guardrails now?")
        if install_now:
            for agent in found_agents:
                record = install_guard(agent, watch=False, shim_dir=DEFAULT_SHIM_DIR)
                ok(f"guard installed for {agent}", record.shim_path)
            settings = _load_claude_settings()
            if not _hook_installed(settings):
                _install_hook(settings)
                _save_claude_settings(settings)
                ok("bash audit hook installed", str(_CLAUDE_SETTINGS_PATH))
            note(f'export PATH="{DEFAULT_SHIM_DIR}:$PATH"')
            console.print()
    elif guards != "no":
        note("no claude binary found in PATH during setup")
        console.print()


@cli.command("docs")
@click.argument("topic", required=False, type=click.Choice(sorted(DOC_TOPICS.keys()), case_sensitive=False))
def docs_cmd(topic):
    """show built-in documentation topics."""
    hero(subtitle="built-in docs", path=os.getcwd())
    command_bar("docs" if topic is None else f"docs {topic}")

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
    """install or inspect direct claude code guardrails."""


@guard_group.command("install")
@click.option("--watch", is_flag=True, help="start canary watch automatically when the shim gates a prompt.")
def guard_install_cmd(watch):
    """install a direct guard shim for claude code."""
    selected = ["claude"]
    hero(subtitle="direct agent guardrails", path=os.getcwd())
    command_bar("guard install")

    installed = False
    for agent in selected:
        try:
            record = install_guard(agent, watch=watch, shim_dir=DEFAULT_SHIM_DIR)
            ok(f"{agent} guard installed", record.shim_path)
            note(f"real binary  {record.real_binary}")
            installed = True
        except RuntimeError as exc:
            warn(f"{agent} not installed", str(exc))
    if installed:
        settings = _load_claude_settings()
        if not _hook_installed(settings):
            _install_hook(settings)
            _save_claude_settings(settings)
            ok("bash audit hook installed", str(_CLAUDE_SETTINGS_PATH))
        console.print()
        note(f'export PATH="{DEFAULT_SHIM_DIR}:$PATH"')
    console.print()


@guard_group.command("status")
def guard_status_cmd():
    """show current direct guard install status."""
    hero(subtitle="direct agent guardrails", path=os.getcwd())
    command_bar("guard status")
    records = guard_records()
    if not records:
        result_panel("[dim]no direct guard shims installed[/dim]\n\n"
                     f'[dim]export PATH="{DEFAULT_SHIM_DIR}:$PATH"[/dim]')
        return

    enabled = get_enabled()
    state_color = BRAND if enabled else "yellow"
    state_label = "on" if enabled else "off"
    lines = [
        f"[dim]shim dir[/dim]   [dim]{DEFAULT_SHIM_DIR}[/dim]",
        f"[dim]screening[/dim]  [{state_color}]{state_label}[/{state_color}]",
        "",
    ]
    for agent, record in records.items():
        lines.append(f"[bold white]{agent}[/bold white]  [dim]{record.shim_path}[/dim]")
        lines.append(f"  [dim]real  {record.real_binary}[/dim]")
        if record.watch:
            lines.append(f"  [dim]watch enabled[/dim]")
    lines += ["", f'[dim]export PATH="{DEFAULT_SHIM_DIR}:$PATH"[/dim]']
    result_panel("\n".join(lines))


@guard_group.command("remove")
def guard_remove_cmd():
    """remove the claude code guard shim."""
    selected = ["claude"]
    hero(subtitle="direct agent guardrails", path=os.getcwd())
    command_bar("guard remove")
    for agent in selected:
        remove_guard(agent)
        ok(f"{agent} guard removed")
    settings = _load_claude_settings()
    if _hook_installed(settings):
        _remove_hook(settings)
        _save_claude_settings(settings)
        ok("bash audit hook removed")
    console.print()


@cli.command("mode")
@click.argument("setting", required=False, type=click.Choice(["local", "online", "status"], case_sensitive=False))
def mode_cmd(setting):
    """switch inference mode between local and online."""
    env_path = str(_env_path())

    def stored_mode():
        values = dotenv_values(env_path)
        local = str(values.get("IBM_LOCAL", "false")).strip().lower() == "true"
        if local:
            return "local", "on-device granite  ·  M1 GPU  ·  no network"
        return "online", "managed cloud inference  ·  watsonx.ai  ·  us-south"

    current, detail = stored_mode()

    if setting is None or setting == "status":
        profile = detect_device_profile()
        hero(subtitle="inference backend", path=os.getcwd())
        command_bar("mode")
        lines = [
            f"[dim]current[/dim]  [{BRAND}]{current}[/{BRAND}]",
            f"[dim]backend[/dim]  [dim]{detail}[/dim]",
            f"[dim]device[/dim]   [dim]{profile.summary}[/dim]",
            "",
            f"[dim]canary mode local   ·  on-device granite[/dim]",
            f"[dim]canary mode online  ·  managed cloud backend[/dim]",
        ]
        if current == "online":
            lines += ["", f"[dim]see canary usage for daily api quota[/dim]"]
        if current == "local" and profile.local_warning:
            lines += ["", f"[yellow]⚠  local mode may run slower on this device[/yellow]"]
        result_panel("\n".join(lines))
        return

    if setting == "local":
        hero(subtitle="inference backend", path=os.getcwd())
        command_bar("mode local")
        _enable_local_mode(
            allow_slow=False,
            install_if_missing=True,
            download_if_missing=True,
        )
        return

    _set_local_mode(False)
    hero(subtitle="inference backend", path=os.getcwd())
    command_bar("mode online")
    ok("online mode", "watsonx.ai · granite-embedding-278m · us-south")
    console.print()


def _usage_bar(used: int, limit: int, width: int = 20) -> str:
    frac = min(used / limit, 1.0) if limit else 0.0
    filled = round(frac * width)
    color = "red" if frac >= 1.0 else ("yellow" if frac >= 0.8 else BRAND)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(frac * 100)
    return f"[{color}]{bar}[/{color}]  [dim]{used}/{limit}  ·  {pct}%[/dim]"


@cli.command("usage")
def usage_cmd():
    """show today's ibm api usage against daily limits."""
    hero(subtitle="api usage", path=os.getcwd())
    command_bar("usage")

    u = get_usage()
    gen = u["generate"]
    emb = u["embed"]

    warn_gen = near_limit("generate")
    warn_emb = near_limit("embed")

    lines = [
        f"[dim]date[/dim]      [dim]{u['date']}[/dim]",
        "",
        f"[dim]text gen[/dim]  {_usage_bar(gen['used'], gen['limit'])}",
    ]
    if warn_gen:
        lines.append(f"  [yellow]⚠  approaching text generation limit[/yellow]")
    lines.append("")
    lines.append(f"[dim]embeddings[/dim]  {_usage_bar(emb['used'], emb['limit'])}")
    if warn_emb:
        lines.append(f"  [yellow]⚠  approaching embedding limit[/yellow]")
    lines += [
        "",
        f"[dim]limits reset at midnight  ·  set CANARY_GENERATE_LIMIT / CANARY_EMBED_LIMIT to override[/dim]",
    ]
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

    console.print(
        f"  [dim]{ts}[/dim]  [{color}]{icon}  {risk}[/{color}]"
        f"  [dim]{category}  ·  {tool} {hook_label}  ·  {via}[/dim]"
    )
    for key in ("command", "file", "what", "repercussions", "found", "note"):
        val = event.get(key)
        if val:
            console.print(f"  [dim]   ╰─ {key:<11}[/dim]  {val}")
    console.print()


def _audit_listen(idle_timeout: int) -> None:
    from rich.rule import Rule

    hero(subtitle="background auditor", path=os.getcwd())
    command_bar("audit")

    start_pos = _AUDIT_EVENTS_PATH.stat().st_size if _AUDIT_EVENTS_PATH.exists() else 0

    console.print(f"  [bold {BRAND}]◉[/bold {BRAND}]  listening for next claude code session")
    console.print(f"  [dim]╰─  events appear as the agent runs  ·  exits after {idle_timeout}s idle[/dim]")
    console.print()
    console.print(Rule(style="dim"))
    console.print()

    last_event_time = time.time()
    event_count = 0

    try:
        while True:
            time.sleep(0.4)
            if not _AUDIT_EVENTS_PATH.exists():
                if (time.time() - last_event_time) >= idle_timeout:
                    break
                continue
            current_size = _AUDIT_EVENTS_PATH.stat().st_size
            if current_size <= start_pos:
                if (time.time() - last_event_time) >= idle_timeout:
                    break
                continue
            with open(_AUDIT_EVENTS_PATH, "r") as fh:
                fh.seek(start_pos)
                new_data = fh.read()
            start_pos = current_size
            for line in new_data.splitlines():
                if not line.strip():
                    continue
                try:
                    _render_audit_event(_json.loads(line))
                    last_event_time = time.time()
                    event_count += 1
                except Exception:
                    pass
    except KeyboardInterrupt:
        pass

    console.print(Rule(style="dim"))
    console.print()
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
@click.option("--idle", default=60, show_default=True,
              help="exit after this many seconds with no audit events.")
@click.option("--stop", is_flag=True, help="stop a running background auditor.")
@click.option("--log", is_flag=True, help="tail the audit log from the last session.")
@click.option("--_bg", is_flag=True, hidden=True)
def audit_cmd(idle, stop, log, _bg):
    """start a background auditor for the next agent session."""
    import subprocess

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

    if _bg:
        _audit_listen(idle_timeout=idle)
        _AUDIT_PID_PATH.unlink(missing_ok=True)
        return

    existing = _audit_already_running()
    if existing:
        hero(subtitle="background auditor", path=os.getcwd())
        command_bar("audit")
        note(f"auditor already running  ·  pid {existing}")
        note(f"canary audit --log   ·  follow output")
        note(f"canary audit --stop  ·  stop it")
        console.print()
        return

    hero(subtitle="background auditor", path=os.getcwd())
    command_bar("audit")

    canary_bin = sys.argv[0]
    cmd = [canary_bin, "audit", "--idle", str(idle), "--_bg"]

    _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_AUDIT_LOG_PATH, "w") as log_file:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
            close_fds=True,
        )
    _AUDIT_PID_PATH.write_text(str(proc.pid))

    result_panel(
        f"[bold {BRAND}]◉[/bold {BRAND}]  auditor running in background\n"
        f"[dim]{'─' * 36}[/dim]\n"
        f"  [dim]│  pid    {proc.pid}[/dim]\n"
        f"  [dim]│  log    {_AUDIT_LOG_PATH}[/dim]\n"
        f"  [dim]│  mode   exits after {idle}s idle[/dim]\n"
        f"[dim]{'─' * 36}[/dim]\n"
        f"  [dim]╰─  canary audit --log   ·  follow output[/dim]\n"
        f"  [dim]╰─  canary audit --stop  ·  stop the auditor[/dim]"
    )


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
    """claude code pretooluse hook: analyses the pending tool use before it runs."""
    from .bash_auditor import audit_command
    from .prompt_firewall import scan_prompt
    from .risk import compute_risk_score
    from .sensitive_files import is_sensitive

    try:
        data = _json.loads(sys.stdin.read())
        tool_name = data.get("tool_name", "")
        inp = data.get("tool_input", {})
    except Exception:
        sys.exit(0)

    try:
        if tool_name == "Bash":
            command = inp.get("command", "").strip()
            if not command:
                sys.exit(0)
            result = audit_command(command)
            via = "granite" if result.via_llm else "pattern"
            _hook_stderr_line(
                "canary audit", result.risk, result.category,
                via,
                [("what", result.what), ("repercussions", result.repercussions)],
            )
            _append_audit_event({
                "tool": "Bash", "risk": result.risk,
                "category": result.category, "via": via,
                "command": command[:120],
                "what": result.what, "repercussions": result.repercussions,
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
                })
    except Exception:
        pass

    sys.exit(0)


_CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

# (event_type, tool_matcher_or_None, hook_command)
# matcher=None means the event has no tool matcher (e.g. UserPromptSubmit)
_HOOK_SPECS: list[tuple[str, str | None, str]] = [
    ("PreToolUse",       "Bash",  "canary audit-hook"),
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


def _hook_installed(settings: dict) -> bool:
    """True if at least the primary audit-hook entry is present."""
    for block in settings.get("hooks", {}).get("PreToolUse", []):
        if block.get("matcher") == "Bash":
            for h in block.get("hooks", []):
                if h.get("command") == "canary audit-hook":
                    return True
    return False


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
        lines.append(f"  {mark}  [dim]{event:<14}  {matcher:<8}  {command}[/dim]")
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
