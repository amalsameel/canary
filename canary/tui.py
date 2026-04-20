from __future__ import annotations

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
