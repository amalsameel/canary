"""Shared terminal styling for canary."""
from rich.console import Console
from rich.table import Table

from . import __version__

console = Console()

BRAND = "#ccff04"
WARN = "yellow"
ERROR = "red"
MUTED = "grey58"
SURFACE = "#2f3136"
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
    left = logo_block() if use_logo else f"  [bold {BRAND}]{MARK}[/bold {BRAND}]"
    left_width = 40 if use_logo else 4
    subtitle_line = subtitle if "[" in subtitle else f"[dim]{subtitle}[/dim]"
    meta_lines = [wordmark(), subtitle_line]
    if path:
        meta_lines.append(f"[dim]{path}[/dim]")
    meta = "\n".join(meta_lines)

    table = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False)
    table.add_column(width=left_width, no_wrap=True)
    table.add_column()
    table.add_row(left, meta)

    console.print()
    console.print(table)
    console.print()


def command_bar(text: str) -> None:
    console.print(f"  > {text}", style=f"bold white on {SURFACE}")
    console.print()


def fields(rows: list[tuple[str, str]]) -> None:
    for label, value in rows:
        console.print(f"  [dim]{label:<10}[/dim] {value}")
    if rows:
        console.print()


def divider(label: str | None = None) -> None:
    if label:
        console.rule(f"[dim]{label}[/dim]", style="dim")
    else:
        console.rule(style="dim")


def ok(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {BRAND}]•[/bold {BRAND}] {text}")
    if detail:
        console.print(f"    [dim]└ {detail}[/dim]")


def warn(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {WARN}]•[/bold {WARN}] {text}")
    if detail:
        console.print(f"    [dim]└ {detail}[/dim]")


def fail(text: str, detail: str | None = None) -> None:
    console.print(f"  [bold {ERROR}]•[/bold {ERROR}] {text}")
    if detail:
        console.print(f"    [dim]└ {detail}[/dim]")


def note(text: str) -> None:
    console.print(f"  [dim]{text}[/dim]")
