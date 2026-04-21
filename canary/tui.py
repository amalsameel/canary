from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.text import Text
from rich import box

BRAND = "#8DF95F"
GLIMMER = "#8F8B86"
WHITE = "#F5F7FA"
MUTED = "#A5AFBA"
FRAME = "#5A6470"
TRACE = "#D7DCE2"
SURFACE = "#171B21"
SURFACE_ALT = "#20262E"

LOGO = """\
[bold #8DF95F]  ███████[/bold #8DF95F]
[bold #8DF95F] ███   ███  ▄▀▄ █▌█ ▄▀▄ █▀▄ █ █[/bold #8DF95F]
[bold #8DF95F] ██         █▄█ █▐█ █▄█ █▀▄ ▐█▌[/bold #8DF95F]
[bold #8DF95F] ███   ███  ▀ ▀ █ █ ▀ ▀ █ █  █[/bold #8DF95F]
[bold #8DF95F]  ███████[/bold #8DF95F]"""


def _shimmer_text(label: str, frame: int) -> Text:
    text = Text()
    if not label:
        return text
    glimmer = _glimmer_indices(label, frame)
    for i, ch in enumerate(label):
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


def _live_activity_text(process: str, frame: int) -> Text:
    return _shimmer_text(f"{process.strip().lower()}...", frame)


def _live_process_label(name: str, detail: str = "") -> str:
    haystack = f"{name} {detail}".lower()
    mappings = (
        (("audit", "review"), "auditing"),
        (("shield", "screen"), "screening"),
        (("semantic", "scan"), "scanning"),
        (("watch",), "watching"),
        (("launch", "forward"), "launching"),
        (("think",), "thinking"),
    )
    for needles, label in mappings:
        if any(needle in haystack for needle in needles):
            return label
    return "processing"


@dataclass
class SubprocessItem:
    """Single subprocess entry with status and optional detail."""
    name: str
    status: Literal["running", "complete", "failed", "pending"] = "pending"
    detail: str = ""

    @property
    def icon(self) -> str:
        icons = {
            "running": "▶",
            "complete": "✓",
            "failed": "✗",
            "pending": "○",
        }
        return icons.get(self.status, "○")


class SubprocessTree:
    """Log-style subprocess display without rectangles."""

    def __init__(self, items: list[SubprocessItem] | None = None) -> None:
        self.items = items or []
        self._frame = 0

    def add_item(self, item: SubprocessItem) -> None:
        self.items.append(item)

    def update_status(self, name: str, status: SubprocessItem.status) -> None:
        for item in self.items:
            if item.name == name:
                item.status = status
                break

    def tick(self) -> None:
        """Animation frame tick."""
        self._frame += 1

    def render(self) -> RenderableType:
        if not self.items:
            return Text("")

        lines: list[Text] = []
        spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        labels = {
            "complete": "done",
            "failed": "failed",
            "pending": "queued",
        }

        last = len(self.items) - 1
        for idx, item in enumerate(self.items):
            # Use spinner for running state, fixed icon otherwise
            if item.status == "running":
                icon = spinners[self._frame % len(spinners)]
            else:
                icon = item.icon

            color = {
                "running": BRAND,
                "complete": BRAND,
                "failed": "red",
                "pending": MUTED,
            }.get(item.status, MUTED)

            branch = "╰─" if idx == last else "├─"
            detail_branch = "   " if idx == last else "│  "

            line = Text()
            line.append(branch, style=f"dim {TRACE}")
            line.append(" ", style=f"dim {TRACE}")
            line.append(icon, style=f"bold {color}")
            line.append(" ", style=f"dim {TRACE}")
            line.append(item.name, style=f"bold {WHITE}")
            line.append("  ", style=f"dim {TRACE}")
            if item.status == "running":
                line.append_text(_live_activity_text(_live_process_label(item.name, item.detail), self._frame))
            else:
                line.append(labels.get(item.status, "queued"), style=f"bold {color}" if item.status != "pending" else f"dim {MUTED}")
            lines.append(line)

            if item.detail:
                detail_line = Text()
                detail_line.append(detail_branch, style=f"dim {TRACE}")
                detail_line.append(" ", style=f"dim {TRACE}")
                detail_line.append(item.detail, style=f"dim {MUTED}")
                lines.append(detail_line)

        return Group(*lines)


class HeaderPanel:
    """Persistent header with logo, version, and cwd."""

    def __init__(self, version: str, cwd: str) -> None:
        self.version = version
        self.cwd = cwd

    def render(self) -> RenderableType:
        logo_text = Text.from_markup(LOGO)
        info = Group(
            Text.from_markup(f"[bold {WHITE}]canary[/bold {WHITE}]  [dim {MUTED}]v{self.version}[/dim {MUTED}]"),
            Text(""),
            Text(self.cwd, style=f"dim {MUTED}"),
        )

        from rich.table import Table
        layout = Table.grid(expand=False, padding=(0, 3))
        layout.add_column(no_wrap=True)
        layout.add_column()
        layout.add_row(logo_text, info)

        return Panel(
            layout,
            border_style=FRAME,
            style=f"{WHITE} on {SURFACE}",
            box=box.HEAVY_EDGE,
            padding=(1, 2),
        )


class PromptArea:
    """Shaded prompt input area with horizontal rules."""

    def __init__(self, prompt: str = "", cursor: str = "▌") -> None:
        self.prompt = prompt
        self.cursor = cursor
        self._frame = 0

    def set_prompt(self, prompt: str) -> None:
        self.prompt = prompt

    def render(self) -> RenderableType:
        import re

        # Horizontal rule
        width = min(80, max(40, 60))
        rule = "─" * width

        # Build styled input line with slash command highlighting
        input_line = Text()
        input_line.append(">", style=f"bold {WHITE}")
        input_line.append("  ", style=WHITE)

        # Tokenize and style: /commands get BRAND color, words get white
        prompt_with_cursor = self.prompt + self.cursor if self.cursor else self.prompt
        tokens = re.findall(r'\S+|\s+', prompt_with_cursor)
        for token in tokens:
            if token.strip().startswith("/"):
                input_line.append(token, style=f"bold {BRAND}")
            else:
                input_line.append(token, style="white")

        content = Group(
            Text(rule, style=f"dim {FRAME}"),
            Text(""),
            input_line,
            Text(""),
            Text(rule, style=f"dim {FRAME}"),
        )

        return Panel(
            content,
            border_style=FRAME,
            style=f"{WHITE} on {SURFACE_ALT}",  # Lighter shading
            box=box.ROUNDED,
            padding=(0, 2),
        )

    def tick(self) -> None:
        """Animation frame tick."""
        self._frame += 1
        cursors = ["▌", "▐", "▖", "▗", "▘", "▙", "▚", "▛", "▜", "▝", "▞", "▟"]
        self.cursor = cursors[self._frame % len(cursors)]


class ThinkingIndicator:
    """Animated thinking indicator with shimmering live-state text."""

    def __init__(self, is_thinking: bool = False) -> None:
        self.is_thinking = is_thinking
        self._frame = 0
        self.pipeline_state: Literal["thinking", "complete"] = "thinking"

    def start_thinking(self) -> None:
        self.is_thinking = True
        self.pipeline_state = "thinking"
        self._frame = 0

    def stop_thinking(self) -> None:
        self.is_thinking = False
        self.pipeline_state = "complete"

    def tick(self) -> None:
        """Animation frame tick."""
        if self.is_thinking:
            self._frame += 1

    def render(self) -> RenderableType:
        if not self.is_thinking and self.pipeline_state == "complete":
            return Text("")  # Hidden when idle

        # Pipeline: thinking → complete
        thinking_style = f"bold {WHITE}" if self.pipeline_state == "thinking" else MUTED
        complete_style = f"bold {BRAND}" if self.pipeline_state == "complete" else MUTED

        content = Text()
        if self.is_thinking:
            content.append_text(_live_activity_text("thinking", self._frame))
        else:
            content.append("thinking", style=thinking_style)
        content.append("  ━━  ", style=f"dim {TRACE}")
        content.append("complete", style=complete_style)

        return Panel(
            content,
            border_style=FRAME,
            style=f"{WHITE} on {SURFACE}",
            box=box.ROUNDED,
            padding=(0, 2),
        )
