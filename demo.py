#!/usr/bin/env python3
"""
canary capability demo — full walkthrough of guard, audit, watch, and rollback.

  python demo.py                       press Enter to advance each step
  AUTO=1 python demo.py                auto-advance with default timing
  AUTO=1 DELAY=1.0 python demo.py      faster auto-advance
"""

import os
import sys
import time

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

console = Console()

AUTO   = os.environ.get("AUTO", "0") == "1"
DELAY  = float(os.environ.get("DELAY", "2.2"))
BRAND  = "#ccff04"


# ── helpers ──────────────────────────────────────────────────────────────────

def pause(secs: float | None = None) -> None:
    if AUTO:
        time.sleep(secs if secs is not None else DELAY)
    else:
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)


def wait(secs: float) -> None:
    """Always sleep regardless of AUTO mode (simulates processing time)."""
    time.sleep(secs)


def cmd(text: str, char_delay: float = 0.045) -> None:
    """Simulate typing a shell command."""
    console.print(f"\n[bold {BRAND}]❯[/bold {BRAND}] ", end="")
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(char_delay)
    console.print()
    wait(0.4)


def section(title: str, hint: str = "") -> None:
    console.print()
    console.rule(f"[dim]{title}[/dim]", style="dim")
    if hint:
        console.print(f"  [dim]{hint}[/dim]")
    console.print()
    pause(0.6 if AUTO else None)


def step(label: str) -> None:
    console.print(f"\n  [dim]·  {label}[/dim]")
    wait(0.3)


def advance_prompt() -> None:
    if not AUTO:
        console.print(f"\n  [dim]─── press Enter to continue ───[/dim]")
        pause()
    else:
        pause()


# ── canary UI primitives (matching real output) ───────────────────────────────

def hero(subtitle: str, path: str = "/home/dev/api-project") -> None:
    meta = f"[bold white]canary[/bold white] [dim]v0.1.0[/dim]\n[dim]{subtitle}[/dim]\n[dim]{path}[/dim]"
    t = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False, expand=False)
    t.add_column(width=4, no_wrap=True)
    t.add_column()
    t.add_row(f"  [bold {BRAND}]◉[/bold {BRAND}]", meta)
    console.print()
    console.print(Panel(t, border_style=BRAND, padding=(1, 3), expand=False))
    console.print()


def bar_cmd(text: str) -> None:
    console.print(f"  [dim]›[/dim] [bold white]{text}[/bold white]", style="on #2f3136")
    console.print()


def ok(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {BRAND}]✓[/bold {BRAND}]  {text}")
    if detail:
        console.print(f"    [dim]╰─  {detail}[/dim]")


def note(text: str) -> None:
    console.print(f"  [dim]·  {text}[/dim]")


def warn(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold yellow]⚠[/bold yellow]  {text}")
    if detail:
        console.print(f"    [dim]╰─  {detail}[/dim]")


def result(content: str) -> None:
    console.print(Panel(content, border_style=BRAND, padding=(1, 3), expand=False))
    console.print()


def audit_hook_line(
    risk: str, category: str, via: str, fields: list[tuple[str, str]]
) -> None:
    RISK_COLOR = {"SAFE": BRAND, "LOW": BRAND, "MEDIUM": "yellow", "HIGH": "red", "CRITICAL": "bold red"}
    RISK_ICON  = {"SAFE": "●", "LOW": "◆", "MEDIUM": "▲", "HIGH": "■", "CRITICAL": "✕"}
    color = RISK_COLOR.get(risk, "white")
    icon  = RISK_ICON.get(risk, "◆")
    console.print(
        f"\n  [bold {color}]{icon}[/bold {color}]  "
        f"[bold]canary audit[/bold]  [{color}]{risk}[/{color}]  "
        f"[dim]{category}  ·  Bash tool  ·  {via}[/dim]"
    )
    for label, value in fields:
        console.print(f"  [dim]   ╰─ {label:<11}[/dim]  {value}")
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# DEMO SEQUENCE
# ─────────────────────────────────────────────────────────────────────────────

def phase_install() -> None:
    section("phase 1 · installation", "install canary")

    cmd("pip install canary-watch")
    wait(0.8)
    console.print("  [dim]Collecting canary-watch[/dim]")
    console.print("  [dim]  Downloading canary_watch-0.1.0-py3-none-any.whl[/dim]")
    console.print("  [dim]Successfully installed canary-watch-0.1.0[/dim]")
    console.print(f"  [bold {BRAND}]✓[/bold {BRAND}]  installed canary-watch")
    wait(0.5)

    advance_prompt()

    cmd("canary setup")
    wait(0.5)
    hero("guided setup", "/home/dev/api-project")
    bar_cmd("setup")
    wait(0.8)
    console.print(f"  [dim]│  device    [/dim]  Apple M2 Pro — 16 GB")
    console.print(f"  [dim]│  recommend [/dim]  online")
    console.print(f"  [dim]│  selected  [/dim]  online")
    console.print()
    ok("online mode", "managed cloud inference ready")
    console.print()
    ok("guard installed for claude", "~/.canary/bin/claude")
    note("real binary  /usr/local/bin/claude")
    console.print()
    ok("bash audit hook installed", "~/.claude/settings.json")
    note('export PATH="$HOME/.canary/bin:$PATH"')
    console.print()

    advance_prompt()


def phase_guard() -> None:
    section("phase 2 · prompt guard", "canary screens every prompt before it reaches Claude")

    cmd("canary on")
    wait(0.4)
    hero("prompt screening", "/home/dev/api-project")
    bar_cmd("on")
    result(
        f"[bold {BRAND}]◉[/bold {BRAND}]  screening [bold white]enabled[/bold white]\n"
        f"[dim]{'─' * 34}[/dim]\n"
        f"  [dim]╰─  all prompts checked before reaching the agent[/dim]\n"
        f"  [dim]╰─  pass [white]-ignore[/white] to bypass for a single call[/dim]"
    )

    advance_prompt()

    cmd('claude "explain the current structure of the API"')
    wait(0.6)
    console.print()
    console.print(f"  [bold {BRAND}]◉[/bold {BRAND}]  canary  [dim]·  reviewing prompt[/dim]")
    wait(1.0)

    t = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False)
    t.add_column(width=12, no_wrap=True)
    t.add_column()
    t.add_row(f"[{BRAND}]●  safe[/{BRAND}]", "[dim]explanation — no sensitive operations detected[/dim]")
    console.print(Panel(t, border_style=BRAND, padding=(1, 2), expand=False))
    console.print()

    console.print("  [dim]╰─  forwarding to claude[/dim]")
    wait(0.8)
    console.print()
    console.rule("[dim]claude[/dim]", style="dim")
    console.print()
    wait(0.6)
    console.print("  The API is an [bold white]Express.js[/bold white] application with four route modules:")
    wait(0.2)
    console.print("  [dim]·[/dim]  [white]routes/users.js[/white]    — user CRUD, no auth middleware yet")
    wait(0.1)
    console.print("  [dim]·[/dim]  [white]routes/products.js[/white] — product catalogue, public endpoints")
    wait(0.1)
    console.print("  [dim]·[/dim]  [white]routes/orders.js[/white]   — order management, needs protection")
    wait(0.1)
    console.print("  [dim]·[/dim]  [white]routes/payments.js[/white] — Stripe integration, unauthenticated")
    wait(0.3)
    console.print()
    console.print("  Recommend adding [bold white]JWT middleware[/bold white] to orders and payments before the next release.")
    console.print()

    advance_prompt()


def phase_checkpoint() -> None:
    section("phase 3 · checkpoint A", "snapshot the workspace before making changes")

    cmd('canary checkpoint --name "checkpoint-a"')
    wait(0.4)
    hero("workspace snapshot", "/home/dev/api-project")
    bar_cmd("checkpoint")
    wait(0.9)
    ok("checkpoint saved", "checkpoint-a")
    console.print()

    advance_prompt()


def phase_activate_monitoring() -> None:
    section("phase 4 · activate monitoring", "start the background auditor and watcher")

    cmd("canary audit")
    wait(0.4)
    hero("background auditor", "/home/dev/api-project")
    bar_cmd("audit")
    result(
        f"[bold {BRAND}]◉[/bold {BRAND}]  auditor running in background\n"
        f"[dim]{'─' * 36}[/dim]\n"
        f"  [dim]│  pid    38471[/dim]\n"
        f"  [dim]│  log    ~/.canary/audit.log[/dim]\n"
        f"  [dim]│  mode   exits after 60s idle[/dim]\n"
        f"[dim]{'─' * 36}[/dim]\n"
        f"  [dim]╰─  canary audit --log   ·  follow output[/dim]\n"
        f"  [dim]╰─  canary audit --stop  ·  stop the auditor[/dim]"
    )

    advance_prompt()

    cmd("canary watch")
    wait(0.4)
    hero("background watcher", "/home/dev/api-project")
    bar_cmd("watch")
    result(
        f"[bold {BRAND}]◉[/bold {BRAND}]  watcher running in background\n"
        f"[dim]{'─' * 36}[/dim]\n"
        f"  [dim]│  pid    38489[/dim]\n"
        f"  [dim]│  log    ~/.canary/watch.log[/dim]\n"
        f"  [dim]│  mode   exits after 30s idle[/dim]\n"
        f"[dim]{'─' * 36}[/dim]\n"
        f"  [dim]╰─  canary watch --log   ·  follow output[/dim]\n"
        f"  [dim]╰─  canary watch --stop  ·  stop the watcher[/dim]"
    )

    advance_prompt()


def phase_risky_session() -> None:
    section("phase 5 · agent session with bash permissions",
            "Claude adds JWT auth — canary intercepts each tool call")

    cmd('claude "add JWT authentication middleware to the orders and payments routes"')
    wait(0.8)
    console.print()
    console.print(f"  [bold {BRAND}]◉[/bold {BRAND}]  canary  [dim]·  reviewing prompt[/dim]")
    wait(1.0)

    t = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False)
    t.add_column(width=16, no_wrap=True)
    t.add_column()
    t.add_row("[yellow]▲  medium[/yellow]", "[dim]auth / security change — agent will modify authentication logic[/dim]")
    console.print(Panel(t, border_style=BRAND, padding=(1, 2), expand=False))
    console.print()

    console.print("  continue? [y/n]  ", end="")
    wait(1.2)
    console.print("[bold white]y[/bold white]")
    wait(0.4)
    console.print(f"  [bold {BRAND}]✓[/bold {BRAND}]  forwarding to claude")
    console.print()
    console.rule("[dim]claude[/dim]", style="dim")
    console.print()
    wait(0.8)

    # Tool call 1 — read existing files (safe)
    console.print("  [dim]Claude is reading the project structure...[/dim]")
    wait(0.6)
    audit_hook_line("LOW", "code restructure", "pattern", [
        ("what",         "reading existing route files for context"),
        ("repercussions","read-only — no side effects"),
    ])
    wait(0.5)

    # Tool call 2 — npm install
    console.print("  Claude wants to run a bash command:")
    console.print("  [dim]  npm install jsonwebtoken bcrypt[/dim]")
    console.print()
    audit_hook_line("MEDIUM", "package install", "granite", [
        ("what",         "installing jsonwebtoken and bcrypt"),
        ("repercussions","adds external dependencies with supply-chain exposure"),
    ])
    console.print("  Allow? [y/n]  ", end="")
    wait(1.4)
    console.print("[bold white]y[/bold white]")
    wait(0.6)
    console.print("  [dim]added 2 packages (jsonwebtoken, bcrypt)[/dim]")
    console.print()

    advance_prompt()

    # Tool call 3 — mkdir
    console.print("  Claude wants to run a bash command:")
    console.print("  [dim]  mkdir -p src/auth[/dim]")
    console.print()
    audit_hook_line("LOW", "code restructure", "pattern", [
        ("what",         "creating auth directory"),
        ("repercussions","local directory creation — reversible"),
    ])
    console.print("  Allow? [y/n]  ", end="")
    wait(1.0)
    console.print("[bold white]y[/bold white]")
    wait(0.4)
    console.print()

    # Tool call 4 — write auth middleware (HIGH — auth content)
    console.print("  Claude wants to write a file:")
    console.print("  [dim]  src/auth/middleware.js[/dim]")
    console.print()
    audit_hook_line("HIGH", "auth / security change", "granite", [
        ("what",         "writing JWT verification middleware"),
        ("repercussions","modifies authentication logic — review carefully"),
    ])
    console.print("  Allow? [y/n]  ", end="")
    wait(1.6)
    console.print("[bold white]y[/bold white]")
    wait(0.5)
    console.print()

    advance_prompt()

    # Tool call 5 — write updated routes (HIGH — auth references)
    console.print("  Claude wants to write a file:")
    console.print("  [dim]  routes/orders.js[/dim]")
    console.print()
    audit_hook_line("HIGH", "auth / security change", "pattern", [
        ("what",         "patching orders route to require authentication"),
        ("repercussions","changes who can access order data"),
    ])
    console.print("  Allow? [y/n]  ", end="")
    wait(1.3)
    console.print("[bold white]y[/bold white]")
    wait(0.4)
    console.print()

    # Tool call 6 — npm test
    console.print("  Claude wants to run a bash command:")
    console.print("  [dim]  npm test[/dim]")
    console.print()
    audit_hook_line("LOW", "testing", "pattern", [
        ("what",         "running the test suite"),
        ("repercussions","read-only — no filesystem changes"),
    ])
    console.print("  Allow? [y/n]  ", end="")
    wait(0.9)
    console.print("[bold white]y[/bold white]")
    wait(0.7)
    console.print("  [dim]PASS  tests/auth.test.js (3 tests)[/dim]")
    console.print("  [dim]PASS  tests/orders.test.js (7 tests)[/dim]")
    console.print(f"  [bold {BRAND}]✓[/bold {BRAND}]  all tests passed")
    console.print()

    console.rule("[dim]session complete[/dim]", style="dim")
    console.print()

    advance_prompt()


def phase_review_logs() -> None:
    section("phase 6 · review what canary caught", "audit log and watch drift report")

    cmd("canary audit --log")
    wait(0.5)
    console.print()
    console.rule("[dim]audit log[/dim]", style="dim")
    console.print()

    events = [
        ("14:02:11", "●", BRAND,    "LOW",    "code restructure",       "read existing routes"),
        ("14:02:19", "▲", "yellow", "MEDIUM", "package install",        "npm install jsonwebtoken bcrypt"),
        ("14:02:31", "◆", BRAND,    "LOW",    "code restructure",       "mkdir -p src/auth"),
        ("14:02:38", "■", "red",    "HIGH",   "auth / security change", "write src/auth/middleware.js"),
        ("14:02:44", "■", "red",    "HIGH",   "auth / security change", "write routes/orders.js"),
        ("14:02:51", "◆", BRAND,    "LOW",    "testing",                "npm test"),
    ]

    for ts, icon, color, risk, category, detail in events:
        console.print(
            f"  [dim]{ts}  │[/dim]  [{color}]{icon}  {risk}[/{color}]"
            f"  [dim]{category}[/dim]"
        )
        console.print(f"  [dim]   ╰─ command      [/dim]  {detail}")
        console.print()
        wait(0.25)

    note("6 audit event(s)  ·  2 HIGH  ·  1 MEDIUM  ·  3 LOW")
    console.print()

    advance_prompt()

    cmd("canary watch --log")
    wait(0.5)
    console.print()
    console.rule("[dim]watch log[/dim]", style="dim")
    console.print()

    watch_events = [
        ("14:02:33", "✦", BRAND,    "created",  "src/auth/"),
        ("14:02:39", "✦", BRAND,    "created",  "src/auth/middleware.js"),
        ("14:02:45", "◆", "white",  "modified", "routes/orders.js"),
        ("14:02:45", "◆", "white",  "modified", "routes/payments.js"),
        ("14:02:47", "◆", "white",  "modified", "package.json"),
        ("14:02:47", "◆", "white",  "modified", "package-lock.json"),
    ]

    for ts, icon, color, etype, rel in watch_events:
        console.print(f"  [dim]{ts}  │[/dim]  [{color}]{icon}[/{color}]  [white]{rel}[/white]")
        if etype == "modified":
            drift = "0.3812" if "orders" in rel else ("0.2941" if "payments" in rel else "0.0211")
            d_color = "red" if float(drift) > 0.3 else ("yellow" if float(drift) > 0.2 else BRAND)
            d_icon  = "■" if float(drift) > 0.3 else ("▲" if float(drift) > 0.2 else "●")
            console.print(f"            [dim]╰─  drift[/dim]  [{d_color}]{'█' * int(float(drift)*20):░<20}[/{d_color}]  [{d_color}]{drift}[/{d_color}]  [{d_color}]{d_icon}[/{d_color}]")
        console.print()
        wait(0.2)

    note("6 file event(s)  ·  2 drift alert(s)")
    console.print()

    advance_prompt()


def phase_rollback() -> None:
    section("phase 7 · rollback to checkpoint A", "restore the workspace to its pre-session state")

    cmd('canary rollback . "checkpoint-a"')
    wait(0.4)
    hero("restore workspace state", "/home/dev/api-project")
    bar_cmd("rollback")

    console.print(f"  [dim]│  snapshot  [/dim]  checkpoint-a")
    console.print(f"  [dim]│  saved     [/dim]  2026-04-19 14:01:44")
    console.print()

    with console.status("[dim]restoring files...[/dim]", spinner="dots"):
        wait(2.0)

    ok("restore complete", "checkpoint-a")
    note("backup saved as rollback_backup_1776596504")
    console.print()

    step("src/auth/middleware.js  removed")
    wait(0.15)
    step("routes/orders.js       restored")
    wait(0.15)
    step("routes/payments.js     restored")
    wait(0.15)
    step("package.json           restored")
    wait(0.15)
    step("package-lock.json      restored")
    console.print()

    advance_prompt()


def phase_summary() -> None:
    section("demo complete")

    lines = [
        f"[bold {BRAND}]◉[/bold {BRAND}]  canary protected the session end-to-end\n"
        f"[dim]{'─' * 40}[/dim]\n"
        f"  [dim]│  prompt guard    [/dim]  screened before claude received the task\n"
        f"  [dim]│  6 tool calls    [/dim]  audited live as claude worked\n"
        f"  [dim]│  2 HIGH alerts   [/dim]  auth middleware writes flagged in real time\n"
        f"  [dim]│  6 file changes  [/dim]  tracked with embedding drift detection\n"
        f"  [dim]│  rollback        [/dim]  workspace restored to checkpoint-a in 2s\n"
        f"[dim]{'─' * 40}[/dim]\n"
        f"  [dim]╰─  canary docs  ·  built-in help topics[/dim]\n"
        f"  [dim]╰─  canary usage ·  daily api quota[/dim]"
    ]
    result("\n".join(lines))


# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    console.print()
    console.print(Panel(
        f"[bold {BRAND}]canary[/bold {BRAND}]  [dim]capability demo[/dim]\n\n"
        f"  [dim]{'auto-advance  (AUTO=1)' if AUTO else 'press Enter to advance each step'}[/dim]\n"
        f"  [dim]Ctrl-C to exit at any time[/dim]",
        border_style=BRAND, padding=(1, 3), expand=False
    ))
    console.print()

    if not AUTO:
        console.print(f"  [dim]press Enter to begin...[/dim]")
        pause()

    phase_install()
    phase_guard()
    phase_checkpoint()
    phase_activate_monitoring()
    phase_risky_session()
    phase_review_logs()
    phase_rollback()
    phase_summary()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]demo interrupted[/dim]\n")
        sys.exit(0)
