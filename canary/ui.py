"""Shared terminal styling for canary."""
from __future__ import annotations

import time

from rich import box
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__

console = Console()

BRAND = "#8DF95F"
WHITE = "#F5F7FA"
WARN = WHITE
ERROR = WHITE
MUTED = "#A5AFBA"
FRAME = "#5A6470"
FRAME_SOFT = "#3C444D"
SURFACE = "#171B21"
SURFACE_ALT = "#20262E"
SUBFOLDER = "•"
LOGO = """\
[bold #8DF95F]  ███████[/bold #8DF95F]
[bold #8DF95F] ███   ███  ▄▀▄ █▌█ ▄▀▄ █▀▄ █ █[/bold #8DF95F]
[bold #8DF95F] ██         █▄█ █▐█ █▄█ █▀▄ ▐█▌[/bold #8DF95F]
[bold #8DF95F] ███   ███  ▀ ▀ █ █ ▀ ▀ █ █  █[/bold #8DF95F]
[bold #8DF95F]  ███████[/bold #8DF95F]"""

_LOADING_GLYPHS = ["◌", "◍", "●", "◍"]
_PULSE_STYLES = [f"bold {BRAND}", f"bold {WHITE}", f"bold {MUTED}", f"bold {BRAND}"]


def _panel_width(max_width: int = 96, min_width: int = 54) -> int:
    return min(max_width, max(min_width, console.size.width - 6))


def _pulse_style(frame: int) -> str:
    return _PULSE_STYLES[frame % len(_PULSE_STYLES)]


def _markup_group(block: str) -> Group:
    lines = block.splitlines() or [""]
    renderables = [Text.from_markup(line) if line else Text("") for line in lines]
    return Group(*renderables)


def _panel_title(label: str | None = None) -> Text:
    text = Text.assemble((" CANARY ", f"bold black on {BRAND}"))
    if label:
        text.append("  ")
        text.append(label.upper(), style=f"bold {WHITE}")
    return text


def _panel_subtitle(label: str | None = None) -> Text | None:
    if not label:
        return None
    return Text(label.upper(), style=f"bold {MUTED}")


def themed_panel(
    content: RenderableType,
    *,
    title: str | Text | None = None,
    subtitle: str | Text | None = None,
    border_style: str = FRAME,
    box_style=box.HEAVY_EDGE,
    width: int | None = None,
    padding: tuple[int, int] = (1, 2),
    expand: bool = False,
) -> Panel:
    if isinstance(title, str):
        title = _panel_title(title)
    if isinstance(subtitle, str):
        subtitle = _panel_subtitle(subtitle)
    return Panel(
        content,
        title=title,
        subtitle=subtitle,
        border_style=border_style,
        style=f"{WHITE} on {SURFACE}",
        box=box_style,
        width=width,
        padding=padding,
        expand=expand,
        title_align="left",
        subtitle_align="left",
    )


def mini_panel(
    content: RenderableType,
    *,
    title: str,
    border_style: str = FRAME,
    frame: int = 0,
) -> Panel:
    label = Text.assemble(
        (" CANARY ", f"bold black on {BRAND}"),
        ("  ", ""),
        (title.upper(), _pulse_style(frame) if border_style == BRAND else f"bold {WHITE}"),
    )
    return themed_panel(
        content,
        title=label,
        border_style=border_style,
        box_style=box.HEAVY_EDGE,
        expand=True,
        padding=(0, 1),
    )


def _soft_line(width: int | None = None, char: str = "─") -> str:
    usable = width or min(64, max(24, console.size.width - 14))
    return char * usable


def _status_chip(label: str, value: str, *, active: bool) -> Text:
    style = f"bold {BRAND}" if active else f"bold {WHITE}"
    return Text.assemble(
        (f" {label.upper()} ", f"bold {MUTED} on {SURFACE_ALT}"),
        (f" {value} ", style),
    )


def _status_row(*, enabled: bool, watcher_running: bool, agent: str) -> Text:
    row = Text()
    chips = [
        _status_chip("screen", "on" if enabled else "off", active=enabled),
        _status_chip("watch", "ready" if watcher_running else "standby", active=watcher_running),
        _status_chip("target", agent, active=True),
    ]
    for index, chip in enumerate(chips):
        row.append_text(chip)
        if index < len(chips) - 1:
            row.append("  ", style="white")
    return row


def _detail_lines(details: list[str]) -> Group:
    lines: list[RenderableType] = []
    for line in details:
        markup = line if "[" in line else f"[dim {MUTED}]{SUBFOLDER} {line}[/dim {MUTED}]"
        lines.append(Text.from_markup(markup))
    return Group(*lines)


def _prompt_block(prompt: str, *, frame: int = 0, active: bool = False) -> Group:
    glyph = _LOADING_GLYPHS[frame % len(_LOADING_GLYPHS)] if active else "●"
    glyph_style = _pulse_style(frame) if active else f"bold {BRAND}"
    row = Text()
    row.append(glyph, style=glyph_style)
    row.append("  ")
    row.append(prompt_preview(prompt, limit=92), style=f"bold {WHITE}" if active else WHITE)
    return Group(
        Text("task", style=f"bold {MUTED}"),
        row,
    )


def _input_line(query: str, frame: int) -> Text:
    cursor = _LOADING_GLYPHS[frame % len(_LOADING_GLYPHS)]
    row = Text()
    row.append(cursor, style=_pulse_style(frame))
    row.append("  ")
    if query:
        row.append(query, style=f"bold {WHITE}")
    else:
        row.append("type a task or :command", style=f"dim {MUTED}")
    return row


def _suggestion_table(suggestions: list[tuple[str, str]]) -> Table:
    table = Table(show_header=False, box=None, padding=(0, 1), pad_edge=False, expand=True)
    table.add_column(width=24, no_wrap=True)
    table.add_column()
    for index, (command, summary) in enumerate(suggestions):
        marker = f"[bold {BRAND}]●[/bold {BRAND}]" if index == 0 else f"[dim {MUTED}]•[/dim {MUTED}]"
        table.add_row(f"{marker}  [bold {WHITE}]{command}[/bold {WHITE}]", f"[dim {MUTED}]{summary}[/dim {MUTED}]")
    return table


def _pipeline_text(states: list[str], frame: int, labels: list[str]) -> Text:
    row = Text(justify="left")
    for index, label in enumerate(labels):
        state = states[index]
        if state == "complete":
            glyph = "●"
            style = f"bold {BRAND}"
        elif state == "active":
            glyph = _LOADING_GLYPHS[frame % len(_LOADING_GLYPHS)]
            style = _pulse_style(frame)
        else:
            glyph = "○"
            style = f"dim {MUTED}"

        row.append(glyph, style=style)
        row.append(f" {label.upper()}", style=style if state != "pending" else WHITE)
        if index < len(labels) - 1:
            connector_style = f"bold {BRAND}" if state in {"complete", "active"} else f"dim {MUTED}"
            row.append("  ━━  ", style=connector_style)
    return row


def logo_block(indent: int = 2) -> str:
    prefix = " " * indent
    return "\n".join(f"{prefix}{line}" for line in LOGO.splitlines())


def wordmark() -> str:
    return f"[bold {WHITE}]canary[/bold {WHITE}]  [dim {MUTED}]v{__version__}[/dim {MUTED}]"


def hero(*, subtitle: str, path: str | None = None, use_logo: bool = False) -> None:
    console.print()
    if use_logo:
        layout = Table.grid(expand=False, padding=(0, 3))
        layout.add_column(no_wrap=True)
        layout.add_column()

        meta: list[RenderableType] = [
            Text.from_markup(wordmark()),
            Text(""),
            Text(subtitle, style=WHITE),
        ]
        if path:
            meta += [Text(""), Text(path, style=f"dim {MUTED}")]
        meta += [
            Text(""),
            Text("Protected launch surface for AI coding sessions.", style=f"dim {MUTED}"),
        ]
        layout.add_row(_markup_group(logo_block(indent=0)), Group(*meta))
        console.print(
            themed_panel(
                layout,
                title="workspace",
                width=min(98, _panel_width(max_width=98, min_width=62)),
                padding=(1, 2),
            )
        )
        console.print()
        return

    rows = Table.grid(padding=(0, 1))
    rows.add_column(width=10, no_wrap=True, style=f"bold {BRAND}")
    rows.add_column()
    rows.add_row("canary", Text.from_markup(wordmark()))
    rows.add_row("context", Text(subtitle, style=WHITE))
    if path:
        rows.add_row("path", Text(path, style=f"dim {MUTED}"))

    console.print(
        themed_panel(
            rows,
            title="status",
            width=min(88, _panel_width(max_width=88, min_width=54)),
            padding=(0, 1),
        )
    )
    console.print()


def command_bar(text: str) -> None:
    row = Text("  ")
    row.append(text.upper(), style=f"bold {WHITE}")
    row.append("  ")
    row.append(_soft_line(30, char="━"), style=FRAME)
    console.print(row)
    console.print()


def fields(rows: list[tuple[str, str]]) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1), pad_edge=False)
    table.add_column(width=12, no_wrap=True, style=f"bold {BRAND}")
    table.add_column()
    for label, value in rows:
        table.add_row(f"{SUBFOLDER} {label}", value)
    if rows:
        console.print(table)
        console.print()


def divider(label: str | None = None) -> None:
    if label:
        console.print(f"[bold {WHITE}]{label.upper()}[/bold {WHITE}] [dim {FRAME}]{_soft_line(44, char='━')}[/dim {FRAME}]")
    else:
        console.print(f"[bold {FRAME}]{_soft_line(56, char='━')}[/bold {FRAME}]")


def ok(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {BRAND}]●[/bold {BRAND}]  {text}")
    if detail:
        console.print(f"     [dim {MUTED}]{SUBFOLDER} {detail}[/dim {MUTED}]")


def warn(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {WHITE}]![/bold {WHITE}]  {text}")
    if detail:
        console.print(f"     [dim {MUTED}]{SUBFOLDER} {detail}[/dim {MUTED}]")


def fail(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {WHITE}]x[/bold {WHITE}]  {text}")
    if detail:
        console.print(f"     [dim {MUTED}]{SUBFOLDER} {detail}[/dim {MUTED}]")


def note(text: str) -> None:
    console.print(f"  [dim {MUTED}]{SUBFOLDER} {text}[/dim {MUTED}]")


def result_panel(content: RenderableType | str, *, padding: tuple = (1, 2)) -> None:
    renderable = _markup_group(content) if isinstance(content, str) else content
    console.print(
        themed_panel(
            renderable,
            title="result",
            width=min(92, _panel_width(max_width=92, min_width=54)),
            padding=padding,
        )
    )
    console.print()


def prompt_preview(text: str, *, limit: int = 64) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1] + "..."


def render_launch_window(
    target: str,
    *,
    heading: str,
    subheading: str,
    query: str | None = None,
    suggestions: list[tuple[str, str]] | None = None,
    prompt: str | None = None,
    footer: str | None = None,
    details: list[str] | None = None,
    enabled: bool = True,
    watcher_running: bool = False,
    agent: str = "ai coding agent",
    pipeline: Text | None = None,
    frame: int = 0,
    command_hints: str = "type : to browse command options",
) -> RenderableType:
    heading_style = _pulse_style(frame) if pipeline is not None else f"bold {WHITE}"
    body: list[RenderableType] = [
        Text.from_markup(wordmark()),
        Text(""),
        Text(heading, style=heading_style),
        Text(subheading, style=MUTED),
        Text(""),
        _status_row(enabled=enabled, watcher_running=watcher_running, agent=agent),
    ]

    if query is not None:
        body += [
            Text(""),
            Text("task or command", style=f"bold {MUTED}"),
            _input_line(query, frame),
        ]
        if suggestions:
            body += [Text(""), _suggestion_table(suggestions[:6])]
        elif query.startswith(("/", ":")):
            body += [Text(""), Text("no matching commands", style=f"dim {MUTED}")]
        else:
            body += [Text(""), Text(command_hints, style=f"dim {MUTED}")]

    if prompt:
        body += [Text(""), _prompt_block(prompt, frame=frame, active=pipeline is not None)]

    if pipeline is not None:
        body += [Text(""), Text("launch sequence", style=f"bold {MUTED}"), pipeline]

    if details:
        body += [Text(""), _detail_lines(details)]

    footer_text = footer or target
    if footer_text:
        body += [Text(""), Text(footer_text, style=f"dim {MUTED}")]

    return themed_panel(
        Group(*body),
        title="launch surface",
        width=_panel_width(max_width=104, min_width=58),
        padding=(1, 2),
    )


def _print_launch_surface(scene: RenderableType) -> None:
    console.clear()
    top_gap = max(1, min(3, console.size.height // 14))
    for _ in range(top_gap):
        console.print()
    console.print(scene)


def protected_prompt_panel(
    target: str,
    *,
    watcher_running: bool = False,
    enabled: bool = True,
    agent: str = "ai coding agent",
) -> str:
    _print_launch_surface(
        render_launch_window(
            target,
            heading="Ready when you are",
            subheading="Enter a task to open a protected AI coding session. Type : for commands.",
            query="",
            enabled=enabled,
            watcher_running=watcher_running,
            agent=agent,
            frame=0,
        )
    )
    return f"[bold {BRAND}]●[/bold {BRAND}]  "


def show_watch_panel(
    target: str,
    *,
    heading: str,
    subheading: str,
    prompt: str | None = None,
    footer: str | None = None,
    active_step: str | None = None,
    agent: str = "ai coding agent",
) -> None:
    labels = ["screen", "watch", agent]
    states = ["pending", "pending", "pending"]
    step_index = {"shield": 0, "watch": 1, "agent": 2, agent: 2}.get(active_step or "", 0)
    for current in range(step_index + 1):
        states[current] = "complete"
    if active_step in {"agent", agent}:
        states[2] = "active"

    _print_launch_surface(
        render_launch_window(
            target,
            heading=heading,
            subheading=subheading,
            query=None,
            prompt=prompt,
            footer=footer,
            enabled=True,
            watcher_running=step_index >= 1,
            agent=agent,
            pipeline=_pipeline_text(states, 0, labels),
        )
    )
    console.print()


def show_launch_brief(
    target: str,
    *,
    heading: str,
    subheading: str,
    details: list[str],
    footer: str | None = None,
    enabled: bool = True,
    watcher_running: bool = False,
    agent: str = "ai coding agent",
) -> None:
    _print_launch_surface(
        render_launch_window(
            target,
            heading=heading,
            subheading=subheading,
            query=None,
            footer=footer,
            details=details,
            enabled=enabled,
            watcher_running=watcher_running,
            agent=agent,
        )
    )
    console.print()


def animate_pipeline(
    prompt: str,
    *,
    agent: str = "ai coding agent",
    target: str | None = None,
    watcher_running: bool = False,
) -> None:
    footer = (
        f"watch already armed  {SUBFOLDER} opening {agent}"
        if watcher_running
        else f"starting watch  {SUBFOLDER} opening {agent}"
    )
    labels = ["screen", "watch", agent]
    states = ["complete", "pending", "pending"]
    dt = 1.0 / 18

    def _frame(frame: int) -> RenderableType:
        footer_text = footer if target is None else f"{footer}  {SUBFOLDER} {target}"
        return render_launch_window(
            target or "",
            heading="Preparing handoff",
            subheading="Review is complete. Finalizing the protected session.",
            query=None,
            prompt=prompt,
            footer=footer_text,
            enabled=True,
            watcher_running=watcher_running or states[1] != "pending",
            agent=agent,
            pipeline=_pipeline_text(states, frame, labels),
            frame=frame,
        )

    console.clear()
    with Live(refresh_per_second=18, console=console, transient=True) as live:
        for frame in range(10):
            live.update(_frame(frame))
            time.sleep(dt)

        states[1] = "active"
        for frame in range(12):
            live.update(_frame(frame))
            time.sleep(dt)

        states[1] = "complete"
        states[2] = "active"
        for frame in range(16):
            live.update(_frame(frame))
            time.sleep(dt)

        states[2] = "complete"
        live.update(_frame(0))
        time.sleep(0.2)
