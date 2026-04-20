"""Risk scoring and prompt rendering."""
from __future__ import annotations

from rich.console import Group
from rich.table import Table
from rich.text import Text

from .ui import BRAND, ERROR, SUBFOLDER, WARN, console, mini_panel, themed_panel

SEVERITY_COLOR = {
    "CRITICAL": f"bold {ERROR}",
    "HIGH": "bold white",
    "MEDIUM": "white",
    "LOW": BRAND,
}

SEVERITY_ICON = {
    "CRITICAL": "!!",
    "HIGH": "!",
    "MEDIUM": ">",
    "LOW": "·",
}

RISK_ASSESSMENT_THRESHOLD = 35


def compute_risk_score(findings: list) -> int:
    return min(sum(f.score for f in findings), 100)


def risk_level(score: int) -> tuple[str, str]:
    if score <= 15:
        return "clear", BRAND
    if score <= 60:
        return "review", WARN
    return "high", ERROR


def bar_color(score: int) -> str:
    return risk_level(score)[1]


def _assessment(score: int) -> tuple[str, str, str, str] | None:
    if score < RISK_ASSESSMENT_THRESHOLD:
        return None
    if score >= 80:
        return (
            "hard stop recommended",
            "This prompt looks too risky to hand off without rewriting it first.",
            "Scrub secrets, paths, and confidential text before you continue.",
            ERROR,
        )
    if score >= 60:
        return (
            "high-risk handoff",
            "This prompt carries enough sensitive signal to justify blocking or rewriting it.",
            "Remove sensitive material before you approve the launch.",
            ERROR,
        )
    return (
        "manual review advised",
        "The prompt is elevated enough to deserve a careful pass before any handoff.",
        "Double-check the prompt before you continue.",
        WARN,
    )


def risk_assessment(score: int) -> tuple[str, str, str, str] | None:
    return _assessment(score)


def render_risk_bar(score: int, label: str = "risk") -> None:
    console.print(
        themed_panel(
            Text.from_markup(_risk_bar_line(score, label=label)),
            title="risk",
            width=min(84, max(52, console.size.width - 6)),
            padding=(0, 1),
        )
    )
    console.print()


def _risk_bar_line(score: int, label: str = "risk") -> str:
    score = max(0, min(100, int(score)))
    verdict, color = risk_level(score)
    filled = max(0, min(20, round(score / 5)))
    bar = "█" * filled + "·" * (20 - filled)
    return (
        f"[bold {BRAND}]{label.upper():<10}[/bold {BRAND}]  "
        f"[{BRAND}]{bar}[/{BRAND}]  "
        f"[bold white]{score:>3}%[/bold white]  "
        f"[bold {color}]{verdict.upper()}[/bold {color}]"
    )


def _findings_table(findings: list) -> Table:
    table = Table(show_header=False, box=None, padding=(0, 1), pad_edge=False)
    table.add_column(width=12, no_wrap=True)
    table.add_column()
    for finding in findings:
        color = SEVERITY_COLOR.get(finding.severity, "white")
        icon = SEVERITY_ICON.get(finding.severity, "·")
        table.add_row(
            f"[{color}]{icon}  {finding.severity.lower()}[/{color}]",
            f"[dim]{finding.description.lower()}[/dim]",
        )
    return table


def _assessment_panel(score: int):
    assessment = risk_assessment(score)
    if assessment is None:
        return None
    headline, summary, action, color = assessment
    body = Group(
        Text.from_markup(f"[bold white]{headline.upper()}[/bold white]"),
        Text.from_markup(f"[dim]{summary}[/dim]"),
        Text.from_markup(f"[bold {color}]{SUBFOLDER} {action}[/bold {color}]"),
    )
    return mini_panel(body, title=f"assessment {score}%", border_style=color)


def render_findings(findings: list, score: int) -> None:
    body: list = []
    if findings:
        body += [
            Text.from_markup("[bold white]FINDINGS[/bold white]"),
            _findings_table(findings),
        ]
    else:
        body.append(Text.from_markup(f"[bold {BRAND}]CLEAR[/bold {BRAND}]  [dim]no findings[/dim]"))

    body += [Text(""), Text.from_markup(_risk_bar_line(score))]
    assessment_panel = _assessment_panel(score)
    if assessment_panel is not None:
        body += [Text(""), assessment_panel]

    console.print(
        themed_panel(
            Group(*body),
            title="prompt review",
            width=min(96, max(56, console.size.width - 6)),
        )
    )
    console.print()
