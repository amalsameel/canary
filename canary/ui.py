"""Shared terminal styling for canary."""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__

console = Console()

BRAND = "#ccff04"
WARN = "yellow"
ERROR = "red"
MUTED = "grey58"
FRAME = "grey46"
SURFACE = "#2b2d30"
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
