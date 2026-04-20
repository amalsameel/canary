"""Risk scoring and prompt rendering."""
from rich.panel import Panel
from rich.table import Table

from .ui import BRAND, FRAME, console

SEVERITY_COLOR = {
    "CRITICAL": "bold red",
    "HIGH":     "red",
    "MEDIUM":   "yellow",
}

SEVERITY_ICON = {
    "CRITICAL": "✕",
    "HIGH":     "■",
    "MEDIUM":   "▲",
    "LOW":      "◆",
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
    console.print(Panel(_risk_bar_line(score, label=label),
                        border_style=FRAME, padding=(1, 3), expand=False))
    console.print()


def _risk_bar_line(score: int, label: str = "risk") -> str:
    score = max(0, min(100, int(score)))
    verdict, color = risk_level(score)
    filled = max(0, min(20, round(score / 5)))
    bar = "█" * filled + "░" * (20 - filled)
    icon = "●" if verdict == "clear" else ("▲" if verdict == "review" else "■")
    return (
        f"[dim]{label:<10}[/dim]  "
        f"[{color}]{bar}[/{color}]  "
        f"[{color}]{score:>3}[/{color}]  "
        f"[{color}]{icon}  {verdict}[/{color}]"
    )


def render_findings(findings: list, score: int) -> None:
    if findings:
        table = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False)
        table.add_column(width=12, no_wrap=True)
        table.add_column()
        for finding in findings:
            color = SEVERITY_COLOR.get(finding.severity, "white")
            icon = SEVERITY_ICON.get(finding.severity, "◆")
            table.add_row(
                f"[{color}]{icon}  {finding.severity.lower()}[/{color}]",
                f"[dim]{finding.description.lower()}[/dim]",
            )
        console.print(Panel(table, border_style=FRAME, padding=(1, 2), expand=False))
        console.print()
    else:
        console.print(Panel(f"[{BRAND}]●[/{BRAND}]  [dim]clear — no findings[/dim]",
                            border_style=FRAME, padding=(1, 3), expand=False))
        console.print()

    console.print(Panel(_risk_bar_line(score), border_style=FRAME, padding=(1, 3), expand=False))
    console.print()
