"""click cli entrypoint."""
import datetime
import json as _json
import os
from pathlib import Path

import click
from dotenv import dotenv_values, load_dotenv, set_key
from rich.table import Table

load_dotenv()

from . import __version__
from .checkpoint import list_checkpoints, rollback as do_rollback, take_snapshot
from .device import detect_device_profile
from .docs_topics import DOC_TOPICS
from .guard import DEFAULT_SHIM_DIR, guard_records, install_guard, remove_guard, resolve_real_binary
from .local_embeddings import ensure_local_model, install_local_dependencies, local_model_cached, missing_local_dependencies
from .prompt_firewall import scan_prompt
from .risk import compute_risk_score, render_findings
from .semantic_firewall import semantic_scan
from .session import log_event, read_log
from .ui import BRAND, command_bar, console, fail, fields, hero, note, ok, warn
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

    rows = [
        ("prompt", "review a prompt before handoff"),
        ("watch", "watch a repo during an agent run"),
        ("checkpoint", "save a clean snapshot"),
        ("rollback", "restore from a snapshot"),
        ("log", "show the event log"),
        ("checkpoints", "list saved snapshots"),
        ("setup", "guided install and backend setup"),
        ("docs", "built-in help topics"),
        ("guard", "install direct claude / codex guardrails"),
        ("mode", "switch inference backend"),
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
def prompt_cmd(text, strict):
    """scan a prompt for sensitive information before sending to an ai agent."""
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

        ok("forwarded")
        console.print()


@cli.command("watch")
@click.argument("target", default=".", type=click.Path(exists=True))
def watch_cmd(target):
    """watch a directory for suspicious agent activity."""
    start_watch(target)


@cli.command("checkpoint")
@click.argument("target", default=".", type=click.Path(exists=True))
def checkpoint_cmd(target):
    """save a clean checkpoint of the current state."""
    hero(subtitle="workspace snapshot", path=os.path.abspath(target))
    command_bar("checkpoint")

    with console.status("[dim]saving snapshot...[/dim]", spinner="dots"):
        checkpoint_id = take_snapshot(target)

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

    console.print(table)
    console.print()
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
    table.add_column("id", width=38, no_wrap=True)
    table.add_column("saved", style="dim")

    for index, checkpoint in enumerate(checkpoints, 1):
        saved = datetime.datetime.fromtimestamp(checkpoint["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        color = "dim" if checkpoint["id"].startswith("rollback_backup") else BRAND
        table.add_row(str(index), f"[{color}]{checkpoint['id']}[/{color}]", saved)

    console.print(table)
    console.print()
    note(f"{len(checkpoints)} snapshot(s)  ·  canary rollback [id]")
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

    found_agents = [agent for agent in ("claude", "codex") if resolve_real_binary(agent, shim_dir=DEFAULT_SHIM_DIR)]
    if guards != "no" and found_agents:
        install_now = guards == "yes" or _confirm("install direct agent guardrails now?")
        if install_now:
            for agent in found_agents:
                record = install_guard(agent, watch=False, shim_dir=DEFAULT_SHIM_DIR)
                ok(f"guard installed for {agent}", record.shim_path)
            note(f'export PATH="{DEFAULT_SHIM_DIR}:$PATH"')
            console.print()
    elif guards != "no":
        note("no claude or codex binary found in PATH during setup")
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
    """install or inspect direct claude/codex guardrails."""


@guard_group.command("install")
@click.option("--agent", "agents", multiple=True, type=click.Choice(["claude", "codex"], case_sensitive=False))
@click.option("--watch", is_flag=True, help="start canary watch automatically when the shim gates a prompt.")
def guard_install_cmd(agents, watch):
    """install direct guard shims for claude and/or codex."""
    selected = list(agents) or ["claude", "codex"]
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
        note("no direct guard shims installed")
        note(f'export PATH="{DEFAULT_SHIM_DIR}:$PATH"')
        console.print()
        return

    fields([("shim dir", str(DEFAULT_SHIM_DIR))])
    for agent, record in records.items():
        ok(agent, record.shim_path)
        note(f"real binary  {record.real_binary}")
        if record.watch:
            note("watch        enabled")
    console.print()
    note(f'export PATH="{DEFAULT_SHIM_DIR}:$PATH"')
    console.print()


@guard_group.command("remove")
@click.option("--agent", "agents", multiple=True, type=click.Choice(["claude", "codex"], case_sensitive=False))
def guard_remove_cmd(agents):
    """remove direct guard shims."""
    selected = list(agents) or ["claude", "codex"]
    hero(subtitle="direct agent guardrails", path=os.getcwd())
    command_bar("guard remove")
    for agent in selected:
        remove_guard(agent)
        ok(f"{agent} guard removed")
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
        fields([
            ("current", f"[{BRAND}]{current}[/{BRAND}]"),
            ("backend", f"[dim]{detail}[/dim]"),
            ("device", f"[dim]{profile.summary}[/dim]"),
        ])
        note("canary mode local   ·  on-device granite")
        note("canary mode online  ·  managed cloud backend")
        if current == "local" and profile.local_warning:
            warn("local mode will run exceptionally slower on this device", profile.summary)
        console.print()
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


if __name__ == "__main__":
    cli()
