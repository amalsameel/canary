"""Shared terminal styling for canary."""
import time

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__

console = Console()

BRAND = "#ccff04"
WARN = "yellow"
ERROR = "red"
MUTED = "grey58"
FRAME = "grey46"
SURFACE = "#2b2d30"
PANEL_SURFACE = "#181a1f"
PANEL_CHROME = "#3f4650"
PANEL_SOFT = "#262b33"
PANEL_TEXT = "#dce3ea"
MARK = "◉"
LOGO = """\
[bold #ccff04]  ███████[/bold #ccff04]
[bold #ccff04] ███   ███  ▄▀▄ █▌█ ▄▀▄ █▀▄ █ █[/bold #ccff04]
[bold #ccff04] ██         █▄█ █▐█ █▄█ █▀▄ ▐█▌[/bold #ccff04]
[bold #ccff04] ███   ███  ▀ ▀ █ █ ▀ ▀ █ █  █[/bold #ccff04]
[bold #ccff04]  ███████[/bold #ccff04]"""


def logo_block(indent: int = 2) -> str:
    prefix = " " * indent
    return "\n".join(f"{prefix}{line}" for line in LOGO.splitlines())


def wordmark() -> str:
    return f"[bold white]canary[/bold white] [dim]v{__version__}[/dim]"


def hero(*, subtitle: str, path: str | None = None, use_logo: bool = False) -> None:
    subtitle_line = subtitle if "[" in subtitle else f"[dim]{subtitle}[/dim]"

    if use_logo:
        meta_lines = [wordmark(), subtitle_line]
        if path:
            meta_lines.append(f"[dim]{path}[/dim]")
        content = logo_block(indent=0) + "\n\n" + "\n".join(meta_lines)
        console.print()
        console.print(Panel(content, border_style=FRAME, padding=(1, 3), expand=False))
        console.print()
        return

    meta_lines = [wordmark(), subtitle_line]
    if path:
        meta_lines.append(f"[dim]{path}[/dim]")
    meta = "\n".join(meta_lines)

    table = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False, expand=False)
    table.add_column(width=4, no_wrap=True)
    table.add_column()
    table.add_row(f"  [bold {BRAND}]{MARK}[/bold {BRAND}]", meta)

    console.print()
    console.print(Panel(table, border_style=FRAME, padding=(1, 3), expand=False))
    console.print()


def command_bar(text: str) -> None:
    console.print(f"  [dim]›[/dim] [bold white]{text}[/bold white]", style=f"on {SURFACE}")
    console.print()


def fields(rows: list[tuple[str, str]]) -> None:
    for label, value in rows:
        console.print(f"  [dim]│  {label:<10}[/dim]  {value}")
    if rows:
        console.print()


def divider(label: str | None = None) -> None:
    if label:
        console.rule(f"[dim]{label}[/dim]", style="dim")
    else:
        console.rule(style="dim")


def ok(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {BRAND}]✓[/bold {BRAND}]  {text}")
    if detail:
        console.print(f"    [dim]╰─  {detail}[/dim]")


def warn(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {WARN}]⚠[/bold {WARN}]  {text}")
    if detail:
        console.print(f"    [dim]╰─  {detail}[/dim]")


def fail(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {ERROR}]✕[/bold {ERROR}]  {text}")
    if detail:
        console.print(f"    [dim]╰─  {detail}[/dim]")


def note(text: str) -> None:
    console.print(f"  [dim]·  {text}[/dim]")


def result_panel(content, *, padding: tuple = (1, 3)) -> None:
    console.print(Panel(content, border_style=FRAME, padding=padding, expand=False))
    console.print()


def prompt_preview(text: str, *, limit: int = 64) -> str:
    """Render a compact one-line preview for prompt/status panels."""
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1] + "..."


# --- Protected launch UI (Claude Code-style) ---

def protected_prompt_panel(target: str, *, watcher_running: bool = False, enabled: bool = True) -> str:
    """Full-width Claude Code-style two-column welcome panel; return the ❯ input prefix."""
    width = min(console.size.width - 2, 110)
    console.clear()

    badge = (
        f"[black on {BRAND}] canary protected [/black on {BRAND}]"
        if enabled
        else "[black on yellow] screening off [/black on yellow]"
    )
    hint_pad = max(2, width - 36)
    console.print(f"  [dim]? for shortcuts[/dim]" + " " * hint_pad + badge)

    # Two-column body: left = C logo + info, sep = │, right = tips + status
    body = Table(show_header=False, box=None, expand=True, show_edge=False, padding=(0, 0))
    body.add_column(ratio=44, justify="center", vertical="middle")
    body.add_column(width=2, justify="center")
    body.add_column(ratio=54)

    left = Text(justify="center")
    left.append("\n")
    for logo_line in LOGO.splitlines():
        left.append_text(Text.from_markup(logo_line + "\n"))
    left.append("\n")
    left.append("ai agent watchdog\n", style="bold white")
    left.append("firewall  ·  audit  ·  rollback\n", style="dim")
    left.append(f"\nv{__version__}\n", style="dim")
    left.append(f"\n{target}\n", style="dim")
    left.append("\n")

    sep = Text(
        "│\n│\n│\n│\n│\n│\n│\n│\n│\n│\n│\n│\n│\n│\n│\n│\n",
        style=PANEL_CHROME,
        justify="center",
    )

    right = Text()
    right.append("\n")
    right.append("Tips for getting started\n", style="bold white")
    right.append("─" * 38 + "\n", style="dim")
    right.append("  canary docs           ", style="dim")
    right.append("built-in help topics\n", style="dim")
    right.append("  canary setup          ", style="dim")
    right.append("configure backend\n", style="dim")
    right.append("  canary guard install  ", style="dim")
    right.append("add hooks to Claude\n", style="dim")
    right.append("─" * 38 + "\n", style="dim")
    right.append("\n")
    right.append("Status\n", style="bold white")
    sc, sl = (BRAND, "on") if enabled else ("yellow", "off")
    right.append("  ● screening  ", style="dim")
    right.append(f"{sl}\n", style=sc)
    wc = BRAND if watcher_running else MUTED
    wl = "running" if watcher_running else "idle"
    right.append("  ● watcher    ", style="dim")
    right.append(f"{wl}\n", style=wc)
    right.append("\n\n\n")

    body.add_row(left, sep, right)

    console.print(Panel(
        body,
        title=f"[dim] Canary v{__version__} [/dim]",
        border_style=PANEL_CHROME,
        style=f"on {PANEL_SURFACE}",
        width=width,
        padding=(0, 1),
    ))
    console.rule(style=PANEL_CHROME)
    return f"[bold {BRAND}]❯[/bold {BRAND}]  "


def show_watch_panel(
    target: str,
    *,
    heading: str,
    subheading: str,
    prompt: str | None = None,
    footer: str | None = None,
    active_step: str | None = None,
) -> None:
    """Full-width status panel for the protected watch flow."""
    width = min(console.size.width - 2, 110)
    console.clear()

    step_specs = [("prompt shield", "shield"), ("watch", "watch"), ("audit", "audit")]
    step_keys = [k for _, k in step_specs]
    try:
        active_idx = step_keys.index(active_step) if active_step else -1
    except ValueError:
        active_idx = -1

    pills = Text()
    for i, (label, _) in enumerate(step_specs):
        if i:
            pills.append("  ━━▶  ", style=BRAND if i <= active_idx else MUTED)
        if i == active_idx:
            pills.append(f" {label} ", style=f"black on {BRAND}")
        elif i < active_idx:
            pills.append(f" ✓ {label} ", style=BRAND)
        else:
            pills.append(f" {label} ", style=f"{PANEL_TEXT} on {PANEL_SOFT}")

    body_items: list = [
        Text(f"\n{heading}", style="bold white"),
        Text(subheading, style=PANEL_TEXT),
        Text(""),
        pills,
    ]
    if prompt:
        body_items += [
            Text(""),
            Text("prompt", style="dim"),
            Text(prompt_preview(prompt, limit=80), style="white"),
        ]
    if footer:
        body_items += [Text(""), Text(footer, style="dim")]
    body_items.append(Text(""))

    console.print(Panel(
        Group(*body_items),
        title=f"[dim] Canary v{__version__} [/dim]",
        border_style=PANEL_CHROME,
        style=f"on {PANEL_SURFACE}",
        width=width,
        padding=(1, 2),
    ))
    console.print()


def animate_pipeline(
    prompt: str,
    *,
    agent: str = "claude",
    target: str | None = None,
    watcher_running: bool = False,
) -> None:
    """Unicode pipeline handoff animation before launching the agent."""
    width = min(console.size.width - 2, 110)
    preview = prompt_preview(prompt, limit=60)
    labels = ["shield", "watch", agent]

    def _pipe(active: int) -> Text:
        t = Text()
        for i, label in enumerate(labels):
            if i:
                t.append("  ━━━▶  ", style=BRAND if i <= active else MUTED)
            node = "◉" if i == active else ("●" if i < active else "○")
            t.append(
                f"{node} {label}",
                style=f"bold {BRAND}" if i == active else (BRAND if i < active else MUTED),
            )
        return t

    footer_text = (
        "reusing the existing watcher and opening Claude now"
        if watcher_running
        else "opening Claude now"
    )

    def _frame(active: int):
        return Panel(
            Group(
                Text("\nSafe prompt accepted", style="bold white"),
                Text(
                    "Canary is handing the request into Claude with session hooks attached.",
                    style=PANEL_TEXT,
                ),
                Text(""),
                _pipe(active),
                Text(""),
                Text("prompt", style="dim"),
                Text(preview, style="white"),
                Text(""),
                Text(footer_text, style="dim"),
                Text(""),
            ),
            title=f"[dim] Canary v{__version__} [/dim]",
            border_style=PANEL_CHROME,
            style=f"on {PANEL_SURFACE}",
            width=width,
            padding=(1, 2),
        )

    console.clear()
    with Live(_frame(0), console=console, refresh_per_second=12, transient=True) as live:
        for active in range(len(labels)):
            live.update(_frame(active))
            time.sleep(0.22)
        live.update(_frame(len(labels) - 1))
        time.sleep(0.3)
