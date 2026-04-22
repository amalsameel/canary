"""Shared terminal styling for canary."""
from __future__ import annotations

from pathlib import Path
import time
from typing import Literal

from rich import box
from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from . import __version__
from .frontend import FRONTEND_CATALOG, ShellCommand

console = Console()

BRAND = "#ccff04"
ACCENT = "#8fd84a"
GLIMMER = "#8f8b86"
WARN = "yellow"
ERROR = "red"
WHITE = "#f4f1eb"
MUTED = "#aaa7a2"
SOFT = "#4a4a46"
TRACE = "#d8d5cf"
FRAME = BRAND
SURFACE = "#171717"
PROMPT_SURFACE = "#2d2d2d"
PROMPT_IDLE = SURFACE
SEARCH_SURFACE = "#232323"

MARK = "◉"
SPINNER_FRAMES = ["⠇", "⠋", "⠙", "⠸", "⠴", "⠦"]
PROCESSING_FRAMES = ["◐", "◓", "◑", "◒", "◴", "◷", "◶", "◵", "✶", "✷", "✹", "✺"]
LOGO = """\
[bold #ccff04]  ███████[/bold #ccff04]
[bold #ccff04] ███   ███  ▄▀▄ █▌█ ▄▀▄ █▀▄ █ █[/bold #ccff04]
[bold #ccff04] ██         █▄█ █▐█ █▄█ █▀▄ ▐█▌[/bold #ccff04]
[bold #ccff04] ███   ███  ▀ ▀ █ █ ▀ ▀ █ █  █[/bold #ccff04]
[bold #ccff04]  ███████[/bold #ccff04]"""
C_MARK = """\
[bold #ccff04]  ███████[/bold #ccff04]
[bold #ccff04] ███   ███[/bold #ccff04]
[bold #ccff04] ██[/bold #ccff04]
[bold #ccff04] ███   ███[/bold #ccff04]
[bold #ccff04]  ███████[/bold #ccff04]"""


def shell_frame_width() -> int:
    return max(60, console.size.width - 2)


def logo_block(indent: int = 2) -> str:
    prefix = " " * indent
    return "\n".join(f"{prefix}{line}" for line in LOGO.splitlines())


def wordmark() -> str:
    return f"[bold white]canary[/bold white] [dim]v{__version__}[/dim]"


def prompt_preview(text: str, *, limit: int = 64) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1] + "..."


def _markup_lines(block: str) -> list[Text]:
    return [Text.from_markup(line) for line in block.splitlines()]


def hero(*, subtitle: str, path: str | None = None, use_logo: bool = False) -> None:
    console.print()
    if use_logo:
        console.print(Align.center(Group(*_markup_lines(LOGO))))
        console.print()
        console.print(Align.center(Text.from_markup(f"[dim]{subtitle}[/dim]")))
        if path:
            console.print(Align.center(Text.from_markup(f"[dim]{path}[/dim]")))
        console.print(Align.center(Text.from_markup(f"[{ACCENT}]{'─' * 44}[/{ACCENT}]")))
        console.print()
        return

    console.print(f"  {wordmark()}")
    console.print(f"  [dim]{subtitle}[/dim]")
    if path:
        console.print(f"  [dim]{path}[/dim]")
    console.print(f"  [{ACCENT}]{'─' * 72}[/{ACCENT}]")
    console.print()


def command_bar(text: str) -> None:
    console.print(f"  [bold {ACCENT}]/{text}[/bold {ACCENT}]")


def fields(rows: list[tuple[str, str]]) -> None:
    for label, value in rows:
        console.print(f"  [dim]{label:<10}[/dim]  {value}")
    if rows:
        console.print()


def divider(label: str | None = None) -> None:
    if label:
        console.rule(f"[dim]{label}[/dim]", style=ACCENT)
    else:
        console.rule(style=ACCENT)


def ok(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {BRAND}]✓[/bold {BRAND}]  {text}")
    if detail:
        console.print(f"    [dim]{detail}[/dim]")


def warn(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {WARN}]⚠[/bold {WARN}]  {text}")
    if detail:
        console.print(f"    [dim]{detail}[/dim]")


def fail(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {ERROR}]✕[/bold {ERROR}]  {text}")
    if detail:
        console.print(f"    [dim]{detail}[/dim]")


def note(text: str) -> None:
    console.print(f"  [dim]·  {text}[/dim]")


def result_panel(content, *, padding: tuple = (1, 3)) -> None:
    del padding
    console.print(f"  [{ACCENT}]{'·' * 72}[/{ACCENT}]")
    if isinstance(content, str):
        for line in content.splitlines():
            console.print(f"  {line}")
    else:
        console.print(content)
    console.print(f"  [{ACCENT}]{'·' * 72}[/{ACCENT}]")
    console.print()


def _short_path(path: str, *, limit: int) -> str:
    home = str(Path.home())
    normalized = f"~{path[len(home):]}" if path.startswith(home) else path
    if len(normalized) <= limit:
        return normalized
    return "…" + normalized[-(limit - 1):]


def shell_header_panel(
    *,
    cwd: str,
    screening_enabled: bool,
    recent_activity: list[str],
    launch_target: str,
    tips: list[ShellCommand] | None = None,
) -> Panel:
    tips = tips or default_shell_tips()
    del recent_activity

    width = shell_frame_width()
    state_color = BRAND if screening_enabled else "yellow"
    shortcuts = "  ".join(tip.name for tip in tips[:4]) or "/agent  /help"
    logo = Align.center(Group(*_markup_lines(LOGO)), vertical="middle")
    body = Group(
        logo,
        Text(""),
        Text.assemble(
            ("canary", f"bold {WHITE}"),
            (f"  v{__version__}", f"dim {MUTED}"),
        ),
        Text.assemble(
            ("screening ", f"dim {MUTED}"),
            ("on" if screening_enabled else "off", f"bold {state_color}"),
            ("  ·  ", f"dim {SOFT}"),
            ("target ", f"dim {MUTED}"),
            (launch_target, f"bold {WHITE}"),
            ("  ·  ", f"dim {SOFT}"),
            ("cwd ", f"dim {MUTED}"),
            (_short_path(cwd, limit=max(18, width - 44)), f"dim {WHITE}"),
        ),
        Text.assemble(
            ("quick ", f"dim {MUTED}"),
            (shortcuts, f"bold {ACCENT}"),
        ),
    )

    title = Text.assemble(
        (" ", BRAND),
        (f"v{__version__}", f"bold {MUTED}"),
        (" ", BRAND),
    )
    return Panel(
        body,
        box=box.ROUNDED,
        border_style=FRAME,
        style=f"on {SURFACE}",
        title=title,
        padding=(0, 1),
        width=width,
    )


def _shimmer_text(label: str, frame: int) -> Text:
    text = Text()
    if not label:
        return text
    glimmer = _glimmer_indices(label, frame)
    for i, ch in enumerate(label):
        # Keep the text itself white and move a grey character sweep across it.
        style = f"bold {GLIMMER}" if i in glimmer else f"bold {WHITE}"
        text.append(ch, style=style)
    return text


def _glimmer_indices(label: str, frame: int, *, window: int = 3) -> set[int]:
    if not label:
        return set()
    span = min(max(1, window), len(label))
    start = (frame % (len(label) + span - 1)) - (span - 1)
    end = start + span
    return set(range(max(0, start), min(len(label), end)))


def live_activity_text(process: str, frame: int) -> Text:
    return _shimmer_text(f"{process.strip().lower()}...", frame)


def _live_process_label(name: str, detail: str = "") -> str:
    haystack = f"{name} {detail}".lower()
    mappings = (
        (("audit", "review"), "auditing"),
        (("shield", "screen"), "screening"),
        (("semantic", "scan"), "scanning"),
        (("watch",), "watching"),
        (("launch", "handoff"), "launching"),
        (("think",), "thinking"),
    )
    for needles, label in mappings:
        if any(needle in haystack for needle in needles):
            return label
    return "processing"


def _prompt_command_length(prompt: str) -> int:
    if not prompt.startswith("/"):
        return 0
    for idx, char in enumerate(prompt):
        if char.isspace():
            return idx
    return len(prompt)


def _pasted_summary_label(word_count: int, line_count: int) -> str:
    word_label = "word" if word_count == 1 else "words"
    line_label = "line" if line_count == 1 else "lines"
    return f"[Pasted text, {word_count} {word_label}, {line_count} {line_label}]"


def _processing_symbol(frame: int | None = None) -> str:
    frame = int(time.time() * 18) if frame is None else frame
    return PROCESSING_FRAMES[frame % len(PROCESSING_FRAMES)]


def _prompt_content_rows(
    prompt: str,
    cursor_pos: int | None,
    lane_width: int,
    *,
    show_paste_summary: bool = False,
    paste_word_count: int = 0,
    paste_line_count: int = 0,
) -> tuple[list[Text], list[int]]:
    visible_prompt = (
        _pasted_summary_label(paste_word_count, paste_line_count)
        if show_paste_summary
        else prompt
    )
    highlight_until = 0 if show_paste_summary else _prompt_command_length(prompt)
    bounded_cursor = None
    if cursor_pos is not None:
        bounded_cursor = len(visible_prompt) if show_paste_summary else max(0, min(cursor_pos, len(prompt)))

    rows = [Text()]
    widths = [0]

    def _push_row() -> None:
        rows.append(Text())
        widths.append(0)

    def _append_piece(piece: str, style: str) -> None:
        remaining = piece
        while remaining:
            if widths[-1] >= lane_width:
                _push_row()
            take = min(len(remaining), lane_width - widths[-1])
            chunk = remaining[:take]
            rows[-1].append(chunk, style=style)
            widths[-1] += len(chunk)
            remaining = remaining[take:]

    def _append_token(token: str, style: str) -> None:
        if token == "\n":
            _push_row()
            return
        if token == "\t":
            _append_piece("    ", style)
            return
        _append_piece(token, style)

    for idx in range(len(visible_prompt) + 1):
        if bounded_cursor is not None and idx == bounded_cursor:
            _append_token("▌", f"bold {BRAND}")
        if idx == len(visible_prompt):
            break
        style = f"bold {BRAND}" if idx < highlight_until else WHITE
        _append_token(visible_prompt[idx], style)

    return rows, widths


def prompt_input_bar(
    prompt: str = "",
    *,
    submitted: bool = False,
    spinner: str = "❯",
    cursor_pos: int = 0,
    line_count: int = 0,
    show_paste_summary: bool = False,
    paste_word_count: int = 0,
    paste_line_count: int = 0,
) -> Group:
    del submitted, line_count
    width = shell_frame_width()
    rule = Text("─" * width, style=WHITE)
    surface = SURFACE
    prefix_len = len(spinner) + 1  # spinner + space
    lane_width = max(1, width - prefix_len)
    rows, widths = _prompt_content_rows(
        prompt,
        cursor_pos,
        lane_width,
        show_paste_summary=show_paste_summary,
        paste_word_count=paste_word_count,
        paste_line_count=paste_line_count,
    )

    rendered_rows: list[Text] = [rule]
    for idx, row in enumerate(rows):
        prompt_line = Text()
        prefix = f"{spinner} " if idx == 0 else " " * prefix_len
        prompt_line.append(prefix, style=f"bold {WHITE} on {surface}")
        prompt_line.append_text(row)
        if widths[idx] < lane_width:
            prompt_line.append(" " * (lane_width - widths[idx]), style=f"{WHITE} on {surface}")
        rendered_rows.append(prompt_line)
    rendered_rows.append(rule.copy())

    return Group(*rendered_rows)


def prompt_choice_bar(
    prompt: str,
    options: list[str],
    *,
    selected_index: int,
    prefix_symbol: str = "❯",
    hint: str | None = None,
) -> Group:
    width = shell_frame_width()
    rule = Text("─" * width, style=WHITE)
    surface = SURFACE
    prefix_len = len(prefix_symbol) + 1
    lane_width = max(1, width - prefix_len)
    rows, widths = _prompt_content_rows(prompt, None, lane_width)

    rendered_rows: list[Text] = [rule]
    for idx, row in enumerate(rows):
        prompt_line = Text()
        prefix = f"{prefix_symbol} " if idx == 0 else " " * prefix_len
        prompt_line.append(prefix, style=f"bold {WHITE} on {surface}")
        row = row.copy()
        row.stylize(f"{WHITE} on {surface}")
        prompt_line.append_text(row)
        if widths[idx] < lane_width:
            prompt_line.append(" " * (lane_width - widths[idx]), style=f"{WHITE} on {surface}")
        rendered_rows.append(prompt_line)

    option_line = Text()
    option_line.append(" " * prefix_len, style=f"bold {WHITE} on {surface}")
    for idx, option in enumerate(options):
        if idx > 0:
            option_line.append("   ", style=f"{WHITE} on {surface}")
        option_style = ACCENT if idx == selected_index else WHITE
        option_line.append(option, style=f"bold {option_style} on {surface}")
    option_width = option_line.cell_len - prefix_len
    if option_width < lane_width:
        option_line.append(" " * (lane_width - option_width), style=f"{WHITE} on {surface}")
    rendered_rows.append(option_line)

    if hint:
        hint_line = Text()
        hint_line.append(" " * prefix_len, style=f"bold {WHITE} on {surface}")
        hint_line.append(hint, style=f"dim {WHITE} on {surface}")
        hint_width = hint_line.cell_len - prefix_len
        if hint_width < lane_width:
            hint_line.append(" " * (lane_width - hint_width), style=f"{WHITE} on {surface}")
        rendered_rows.append(hint_line)

    rendered_rows.append(rule.copy())
    return Group(*rendered_rows)


def submitted_prompt_bar(
    prompt: str,
    *,
    status: Literal["running", "complete", "failed"] = "running",
    symbol: str | None = None,
) -> Group:
    width = shell_frame_width()
    surface = PROMPT_SURFACE
    if status == "running":
        icon = symbol or _processing_symbol()
        icon_color = ACCENT
    elif status == "failed":
        icon = symbol or "✕"
        icon_color = ERROR
    else:
        icon = symbol or "✓"
        icon_color = ACCENT

    prefix_len = len(icon) + 1
    lane_width = max(1, width - prefix_len)
    rows, widths = _prompt_content_rows(prompt, None, lane_width)

    rendered_rows: list[Text] = []
    for idx, row in enumerate(rows):
        prompt_line = Text()
        prefix = f"{icon} " if idx == 0 else " " * prefix_len
        prefix_style = f"bold {icon_color} on {surface}" if idx == 0 else f"{WHITE} on {surface}"
        row = row.copy()
        row.stylize(f"on {surface}")
        prompt_line.append(prefix, style=prefix_style)
        prompt_line.append_text(row)
        if widths[idx] < lane_width:
            prompt_line.append(" " * (lane_width - widths[idx]), style=f"{WHITE} on {surface}")
        rendered_rows.append(prompt_line)

    return Group(*rendered_rows)


def prompt_rules() -> tuple[Text, Text]:
    width = shell_frame_width()
    rule = Text("─" * width, style=WHITE)
    return rule, rule.copy()


def surveillance_items(prompt: str, cwd: str, agent: str, frame: int) -> Group:
    preview = prompt_preview(prompt, limit=52)
    stages = [
        ("prompt shield", f"screening '{preview}'"),
        ("semantic scan", f"comparing anchors in {cwd}"),
        ("launch target", f"waiting to hand off into {agent}"),
    ]
    rows: list[RenderableType] = []
    active = (frame // 6) % len(stages)
    for idx, (name, detail) in enumerate(stages):
        branch = "╰─" if idx == len(stages) - 1 else "├─"
        detail_branch = "   " if idx == len(stages) - 1 else "│  "
        icon = SPINNER_FRAMES[frame % len(SPINNER_FRAMES)] if idx == active else "•"
        line = Text()
        line.append(branch, style=f"dim {TRACE}")
        line.append(" ", style=f"dim {TRACE}")
        line.append(icon, style=f"bold {ACCENT}" if idx == active else f"dim {MUTED}")
        line.append(" ", style=f"dim {TRACE}")
        line.append(name, style=f"bold {WHITE}")
        line.append("  ", style=f"dim {TRACE}")
        if idx == active:
            line.append_text(live_activity_text(_live_process_label(name, detail), frame))
        else:
            line.append("waiting", style=f"dim {MUTED}")
        rows.append(line)

        detail_line = Text()
        detail_line.append(detail_branch, style=f"dim {TRACE}")
        detail_line.append(" ", style=f"dim {TRACE}")
        detail_line.append(detail, style=f"dim {WHITE}" if idx == active else f"dim {MUTED}")
        rows.append(detail_line)
    return Group(*rows)


def shell_scene(
    *,
    cwd: str,
    screening_enabled: bool,
    recent_activity: list[str],
    launch_target: str,
    prompt: str = "",
    submitted: bool = False,
    spinner: str = "❯",
    status: RenderableType | None = None,
    submitted_prompt: str | None = None,
    submitted_prompt_state: Literal["running", "complete", "failed"] = "running",
    submitted_prompt_symbol: str | None = None,
    tips: list[ShellCommand] | None = None,
    show_prompt_lane: bool = True,
    prompt_lane: RenderableType | None = None,
    editor_suggestions: RenderableType | None = None,
    cursor_pos: int = 0,
    line_count: int = 0,
    show_paste_summary: bool = False,
    paste_word_count: int = 0,
    paste_line_count: int = 0,
) -> Group:
    body: list[RenderableType] = [
        shell_header_panel(
            cwd=cwd,
            screening_enabled=screening_enabled,
            recent_activity=recent_activity,
            launch_target=launch_target,
            tips=tips,
        ),
    ]
    if submitted_prompt:
        body.append(
            submitted_prompt_bar(
                submitted_prompt,
                status=submitted_prompt_state,
                symbol=submitted_prompt_symbol,
            )
        )
    if status is not None:
        body.append(status)
    if show_prompt_lane:
        if prompt_lane is not None:
            body.append(prompt_lane)
        else:
            body.append(
                prompt_input_bar(
                    prompt,
                    submitted=submitted,
                    spinner=spinner,
                    cursor_pos=cursor_pos,
                    line_count=line_count,
                    show_paste_summary=show_paste_summary,
                    paste_word_count=paste_word_count,
                    paste_line_count=paste_line_count,
                )
            )
        if prompt_lane is None and editor_suggestions is not None:
            body.append(editor_suggestions)
    return Group(*body)


def animate_surveillance(prompt: str, *, cwd: str, agent: str, recent_activity: list[str], screening_enabled: bool) -> None:
    """Show subprocess-style surveillance animation."""
    subprocess_log = SubprocessLog()
    preview = prompt_preview(prompt, limit=34)
    subprocess_log.add("prompt", f"submitted '{preview}'", "complete")
    subprocess_log.add("shield", f"screening '{preview}'", "running")
    subprocess_log.add("semantic scan", f"comparing anchors in {cwd}", "pending")
    subprocess_log.add("launch target", f"waiting to hand off into {agent}", "pending")

    frame = 0
    def _frame() -> Group:
        subprocess_log.tick()
        return shell_scene(
            cwd=cwd,
            screening_enabled=screening_enabled,
            recent_activity=recent_activity,
            launch_target=agent,
            prompt="",
            submitted=False,
            spinner=SPINNER_FRAMES[frame % len(SPINNER_FRAMES)],
            status=subprocess_log.render(),
            submitted_prompt=prompt,
            submitted_prompt_state="running",
            tips=_default_shell_tips(),
        )

    console.clear()
    with Live(console=console, refresh_per_second=12, transient=True) as live:
        for frame in range(12):
            live.update(_frame())
            time.sleep(0.08)
        subprocess_log.update("shield", "complete", "prompt cleared")
        subprocess_log.update("semantic scan", "running")

        for frame in range(12, 24):
            live.update(_frame())
            time.sleep(0.08)
        subprocess_log.update("semantic scan", "complete", "anchors compared")
        subprocess_log.update("launch target", "pending" if not agent else "running")

        for frame in range(24, 36):
            live.update(_frame())
            time.sleep(0.055)


def subprocess_overview_log(
    *,
    screening_enabled: bool,
    audit_active: bool,
    watch_active: bool,
    watch_target: str | None = None,
    launch_target: str = "ai agent",
    active_step: Literal["shield", "audit", "watch", "launch"] | None = None,
    audit_external: bool = False,
) -> SubprocessLog:
    subprocess_log = SubprocessLog(animated=False)

    shield_status: SubprocessStatus
    if active_step == "shield":
        shield_status = "running"
    elif screening_enabled:
        shield_status = "complete"
    else:
        shield_status = "idle"
    if active_step in {None, "shield", "launch"}:
        subprocess_log.add(
            "shield",
            "prompt firewall armed" if screening_enabled else "prompt firewall paused",
            shield_status,
        )

    # Only show audit in subprocess log if it's not running in external terminal
    if not audit_external:
        audit_status: SubprocessStatus = "running" if active_step == "audit" or audit_active else "idle"
        if audit_active or active_step == "audit":
            subprocess_log.add(
                "audit",
                "companion audit stream live" if audit_active else "companion audit stream idle",
                audit_status,
            )

    watch_status: SubprocessStatus = "running" if active_step == "watch" or watch_active else "idle"
    if watch_active and watch_target:
        watch_detail = f"main-terminal watch stream live for {_short_path(watch_target, limit=42)}"
    elif watch_active:
        watch_detail = "main-terminal watch stream live"
    elif active_step == "watch" and watch_target:
        watch_detail = f"starting main-terminal watch stream for {_short_path(watch_target, limit=42)}"
    else:
        watch_detail = "main-terminal watch stream idle"
    if watch_active or active_step == "watch":
        subprocess_log.add("watch", watch_detail, watch_status)

    launch_ready = bool(launch_target and launch_target != "no launch target")
    if active_step == "launch":
        launch_status: SubprocessStatus = "running"
    elif launch_ready:
        launch_status = "complete"
    else:
        launch_status = "idle"
    if active_step in {None, "launch"}:
        subprocess_log.add(
            "launch target",
            f"launch target set to {launch_target}" if launch_ready else "launch target not set",
            launch_status,
        )

    return subprocess_log


def subprocess_overview(
    *,
    screening_enabled: bool,
    audit_active: bool,
    watch_active: bool,
    watch_target: str | None = None,
    launch_target: str = "ai agent",
    active_step: Literal["shield", "audit", "watch", "launch"] | None = None,
    audit_external: bool = False,
) -> RenderableType:
    return subprocess_overview_log(
        screening_enabled=screening_enabled,
        audit_active=audit_active,
        watch_active=watch_active,
        watch_target=watch_target,
        launch_target=launch_target,
        active_step=active_step,
        audit_external=audit_external,
    ).render()


def protected_prompt_panel(
    target: str,
    *,
    audit_active: bool = False,
    watcher_running: bool = False,
    watch_target: str | None = None,
    enabled: bool = True,
    launch_target: str = "ai agent",
) -> str:
    console.clear()
    console.print(shell_scene(
        cwd=target,
        screening_enabled=enabled,
        recent_activity=[],
        launch_target=launch_target,
        status=subprocess_overview(
            screening_enabled=enabled,
            audit_active=audit_active,
            watch_active=watcher_running,
            watch_target=watch_target,
            launch_target=launch_target,
        ),
        tips=_default_shell_tips(),
        show_prompt_lane=False,
    ))
    return "❯"


def show_watch_panel(
    target: str,
    *,
    heading: str,
    subheading: str,
    prompt: str | None = None,
    footer: str | None = None,
    active_step: str | None = None,
    launch_target: str = "ai agent",
) -> None:
    step_name = active_step if active_step in {"shield", "audit", "watch"} else None
    lines = [Text.from_markup(f"[bold white]{heading}[/bold white]"), Text.from_markup(f"[dim]{subheading}[/dim]")]
    if prompt:
        lines.append(Text.from_markup(f"[white]\"{prompt_preview(prompt, limit=96)}\"[/white]"))
    lines.append(Text(""))
    lines.append(subprocess_overview(
        screening_enabled=True,
        audit_active=step_name == "audit",
        watch_active=step_name == "watch",
        watch_target=target if step_name == "watch" else None,
        launch_target=launch_target,
        active_step=step_name,
    ))
    if active_step and active_step not in {"shield", "audit", "watch"}:
        lines.append(Text.from_markup(f"[bold {ACCENT}]{active_step}[/bold {ACCENT}]"))
    if footer:
        lines.append(Text(""))
        lines.append(Text.from_markup(f"[dim]{footer}[/dim]"))

    console.clear()
    console.print(shell_scene(
        cwd=target,
        screening_enabled=True,
        recent_activity=["Prompt accepted", "watch subprocess staged"],
        launch_target=launch_target,
        prompt=prompt or "",
        submitted=bool(prompt),
        spinner="●" if prompt else "❯",
        status=Group(*lines),
        submitted_prompt=prompt or None,
        submitted_prompt_state="complete" if prompt else "running",
        tips=_default_shell_tips(),
    ))


def animate_pipeline(
    prompt: str,
    *,
    agent: str = "ai agent",
    target: str | None = None,
    audit_active: bool = False,
    watcher_running: bool = False,
    watch_target: str | None = None,
) -> None:
    """Show subprocess-style animation for the pipeline."""
    subprocess_log = SubprocessLog()
    subprocess_log.add("prompt", f"submitted '{prompt_preview(prompt, limit=34)}'", "complete")
    subprocess_log.add("shield", "reviewing prompt", "running")
    if audit_active:
        subprocess_log.add("audit", "companion audit stream live", "running")
    if watcher_running and watch_target:
        watch_detail = f"main-terminal watch stream live for {_short_path(watch_target, limit=42)}"
        subprocess_log.add("watch", watch_detail, "running")
    elif watcher_running:
        subprocess_log.add("watch", "main-terminal watch stream live", "running")
    subprocess_log.add(agent.title().lower(), "waiting to launch session", "pending")

    def _render(frame: int) -> Group:
        subprocess_log.tick()
        return shell_scene(
            cwd=target or "",
            screening_enabled=True,
            recent_activity=["Prompt cleared", "Preparing live handoff"],
            launch_target=agent,
            prompt="",
            submitted=False,
            spinner=SPINNER_FRAMES[frame % len(SPINNER_FRAMES)],
            status=subprocess_log.render(),
            submitted_prompt=prompt,
            submitted_prompt_state="running",
            tips=_default_shell_tips(),
        )

    console.clear()
    with Live(console=console, refresh_per_second=12, transient=True) as live:
        # Stage 1: screening running
        for frame in range(12):
            live.update(_render(frame))
            time.sleep(0.08)
        subprocess_log.update("shield", "complete", "prompt cleared")
        subprocess_log.update(agent.title().lower(), "running", "starting agent handoff")

        # Stage 2: launch handoff
        for frame in range(12, 24):
            live.update(_render(frame))
            time.sleep(0.08)

        # Stage 3: launching agent
        for frame in range(24, 36):
            live.update(_render(frame))
            time.sleep(0.05)


SubprocessStatus = Literal["running", "complete", "failed", "pending", "idle"]


class SubprocessLog:
    """Log-style subprocess display without rectangles."""

    def __init__(self, *, animated: bool = True) -> None:
        self.items: list[tuple[str, str, SubprocessStatus, str]] = []
        self._frame = 0
        self._animated = animated

    def add(self, name: str, detail: str = "", status: SubprocessStatus = "pending") -> None:
        self.items.append((name, detail, status, ""))

    def update(self, name: str, status: SubprocessStatus, detail: str = "") -> None:
        for i, (n, d, s, spinner) in enumerate(self.items):
            if n == name:
                self.items[i] = (n, detail or d, status, spinner)
                break

    def tick(self) -> None:
        self._frame += 1

    def merged(self, *others: "SubprocessLog", animated: bool | None = None) -> "SubprocessLog":
        merged = SubprocessLog(
            animated=animated if animated is not None else self._animated or any(other._animated for other in others)
        )
        merged._frame = max([self._frame, *(other._frame for other in others)], default=0)
        merged.items = list(self.items)
        for other in others:
            merged.items.extend(other.items)
        return merged

    def render(self) -> RenderableType:
        if not self.items:
            return Text("")

        lines: list[Text] = []
        spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        labels = {
            "complete": "done",
            "failed": "failed",
            "idle": "idle",
            "pending": "queued",
        }

        last = len(self.items) - 1
        for idx, (name, detail, status, _) in enumerate(self.items):
            icon = {
                "running": spinners[self._frame % len(spinners)],
                "complete": "✓",
                "failed": "✗",
                "idle": "◌",
                "pending": "○",
            }.get(status, "○")

            color = {
                "running": ACCENT,
                "complete": ACCENT,
                "failed": ERROR,
                "idle": MUTED,
                "pending": MUTED,
            }.get(status, MUTED)

            branch = "╰─" if idx == last else "├─"
            detail_branch = "   " if idx == last else "│  "

            line = Text()
            line.append(branch, style=f"dim {TRACE}")
            line.append(" ", style=f"dim {TRACE}")
            line.append(icon, style=f"bold {color}")
            line.append(" ", style=f"dim {TRACE}")
            line.append(name, style=f"bold {WHITE}")
            line.append("  ", style=f"dim {TRACE}")
            if status == "running":
                if self._animated:
                    line.append_text(live_activity_text(_live_process_label(name, detail), self._frame))
                else:
                    line.append("running", style=f"bold {ACCENT}")
            else:
                label_style = f"bold {color}" if status in {"complete", "failed"} else f"dim {MUTED}"
                line.append(labels.get(status, "queued"), style=label_style)
            lines.append(line)

            if detail:
                detail_line = Text()
                detail_line.append(detail_branch, style=f"dim {TRACE}")
                detail_line.append(" ", style=f"dim {TRACE}")
                detail_line.append(detail, style=f"dim {MUTED}")
                lines.append(detail_line)

        return Group(*lines)


def _default_shell_tips() -> list[ShellCommand]:
    return [FRONTEND_CATALOG.commands[0], FRONTEND_CATALOG.commands[1]]


def default_shell_tips() -> list[ShellCommand]:
    return _default_shell_tips()
