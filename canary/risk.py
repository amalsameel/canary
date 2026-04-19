"""Risk scoring and prompt rendering."""
from rich.table import Table

from .ui import BRAND, console, divider, ok

SEVERITY_COLOR = {
    "CRITICAL": "bold red",
    "HIGH": "red",
    "MEDIUM": "yellow",
}


def compute_risk_score(findings: list) -> int:
    return min(sum(f.score for f in findings), 100)


def risk_level(score: int) -> tuple[str, str]:
    if score <= 15:
        return "clear", BRAND
    if score <= 60:
        return "review", "yellow"
    return "high", "red"


def bar_color(score: int) -> str:
    return risk_level(score)[1]


def render_risk_bar(score: int, label: str = "risk") -> None:
    score = max(0, min(100, int(score)))
    verdict, color = risk_level(score)
    filled = max(0, min(20, round(score / 5)))
    bar = "█" * filled + "░" * (20 - filled)
    console.print(
        f"  [dim]{label:<10}[/dim]  "
        f"[{color}]{bar}[/{color}]  "
        f"[{color}]{score:>3}[/{color}]  "
        f"[{color}]{verdict}[/{color}]"
    )


def render_findings(findings: list, score: int) -> None:
    if findings:
        divider("findings")
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 1), pad_edge=False)
        table.add_column(width=10, no_wrap=True)
        table.add_column()

        for finding in findings:
            color = SEVERITY_COLOR.get(finding.severity, "white")
            table.add_row(
                f"[{color}]{finding.severity.lower()}[/{color}]",
                f"[white]{finding.description.lower()}[/white]",
            )

        console.print(table)
        console.print()
    else:
        divider("result")
        console.print()
        ok("clear")
        console.print()

    divider("risk")
    console.print()
    render_risk_bar(score)
    console.print()
