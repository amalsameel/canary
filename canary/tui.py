from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.text import Text
from rich import box

BRAND = "#8DF95F"
WHITE = "#F5F7FA"
MUTED = "#A5AFBA"
FRAME = "#5A6470"
SURFACE = "#171B21"
SURFACE_ALT = "#20262E"

LOGO = """\
[bold #8DF95F]  ███████[/bold #8DF95F]
[bold #8DF95F] ███   ███  ▄▀▄ █▌█ ▄▀▄ █▀▄ █ █[/bold #8DF95F]
[bold #8DF95F] ██         █▄█ █▐█ █▄█ █▀▄ ▐█▌[/bold #8DF95F]
[bold #8DF95F] ███   ███  ▀ ▀ █ █ ▀ ▀ █ █  █[/bold #8DF95F]
[bold #8DF95F]  ███████[/bold #8DF95F]"""


class PromptArea:
    """Shaded prompt input area with horizontal rules."""

    def __init__(self, prompt: str = "", cursor: str = "▌") -> None:
        self.prompt = prompt
        self.cursor = cursor
        self._frame = 0

    def set_prompt(self, prompt: str) -> None:
        self.prompt = prompt

    def render(self) -> RenderableType:
        # Horizontal rule
        width = min(80, max(40, 60))
        rule = "─" * width

        # Input line with cursor
        display = self.prompt + self.cursor if self.cursor else self.prompt
        input_line = Text.from_markup(f"[bold {WHITE}]>[/bold {WHITE}]  {display}")

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


@dataclass
class SubprocessItem:
    """Single subprocess entry."""
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
    """Tree display of subprocesses with Unicode branch characters."""

    def __init__(self, items: list[SubprocessItem] | None = None) -> None:
        self.items = items or []

    def add_item(self, item: SubprocessItem) -> None:
        self.items.append(item)

    def update_status(self, name: str, status: SubprocessItem.status) -> None:
        for item in self.items:
            if item.name == name:
                item.status = status
                break

    def render(self) -> RenderableType:
        if not self.items:
            return Text("")  # Empty if no items

        lines: list[RenderableType] = []
        for i, item in enumerate(self.items):
            is_last = i == len(self.items) - 1
            branch = "└──" if is_last else "├──"
            style = {
                "running": f"bold {BRAND}",
                "complete": f"bold {BRAND}",
                "failed": "bold white",
                "pending": MUTED,
            }.get(item.status, MUTED)

            line = Text.from_markup(
                f"[dim {MUTED}]{branch}[/dim {MUTED}]  "
                f"[{style}]{item.icon}[/{style}]  "
                f"{item.name}"
            )
            if item.detail:
                line.append_text(Text.from_markup(f"  [dim {MUTED}]{item.detail}[/dim {MUTED}]"))
            lines.append(line)

            # Add vertical connector if not last
            if not is_last:
                lines.append(Text.from_markup(f"[dim {MUTED}]│[/dim {MUTED}]"))

        return Panel(
            Group(*lines),
            border_style=FRAME,
            style=f"{WHITE} on {SURFACE}",
            box=box.ROUNDED,
            padding=(1, 2),
            title="activity",
            title_align="left",
        )


class ThinkingIndicator:
    """Animated thinking indicator with ●/○ pulse and pipeline state."""

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

        # Pulse between ● and ○
        glyphs = ["●", "○"]
        glyph = glyphs[self._frame % 2] if self.is_thinking else "●"
        glyph_style = f"bold {BRAND}" if self.is_thinking else MUTED

        # Pipeline: thinking → complete
        thinking_style = f"bold {BRAND}" if self.pipeline_state == "thinking" else MUTED
        complete_style = f"bold {BRAND}" if self.pipeline_state == "complete" else MUTED

        content = Text()
        content.append(glyph, style=glyph_style)
        content.append("  ")
        content.append("thinking", style=thinking_style)
        content.append("  ━━  ", style=f"dim {FRAME}")
        content.append("complete", style=complete_style)

        return Panel(
            content,
            border_style=FRAME,
            style=f"{WHITE} on {SURFACE}",
            box=box.ROUNDED,
            padding=(0, 2),
        )
