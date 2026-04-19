"""wrapper commands that gate prompts before handing them to coding agents."""
import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

from .prompt_firewall import scan_prompt
from .risk import compute_risk_score, render_findings
from .semantic_firewall import semantic_scan
from .session import log_event
from .ui import command_bar, console, fail, hero, note, ok


@dataclass
class WatchSidecar:
    process: subprocess.Popen
    stream: object
    log_path: str


def _normalize_forwarded_args(args: list[str]) -> list[str]:
    if args and args[0] == "--":
        return args[1:]
    return args


def _build_parser(prog: str, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument(
        "--mode",
        choices=["interactive", "once"],
        default="interactive",
        help="interactive opens the full session; once runs a single checked prompt and exits",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="shortcut for --mode once",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="run canary watch in the background during the agent session",
    )
    parser.add_argument(
        "--watch-dir",
        default=os.environ.get("CANARY_WATCH_DIR", "."),
        help="directory to watch when --watch is enabled (default: current directory)",
    )
    parser.add_argument("prompt", help="initial prompt to gate and forward")
    parser.add_argument(
        "agent_args",
        nargs=argparse.REMAINDER,
        help="extra agent args to forward after `--`",
    )
    return parser


def _run_prompt_gate(prompt: str, target: str) -> None:
    hero(subtitle="agent wrapper", path=target)
    command_bar("prompt review")

    findings = scan_prompt(prompt)
    with console.status("[dim]reviewing...[/dim]", spinner="dots"):
        findings += semantic_scan(prompt)

    score = compute_risk_score(findings)
    render_findings(findings, score)

    log_event("prompt_scan", {
        "score": score,
        "finding_count": len(findings),
        "severities": [f.severity for f in findings],
    }, target=target)

    if findings:
        fail("blocked", "stopping before the agent receives the prompt")
        console.print()
        raise SystemExit(1)


def _start_watch_sidecar(watch_dir: str, label: str) -> WatchSidecar:
    canary_dir = os.path.join(watch_dir, ".canary")
    os.makedirs(canary_dir, exist_ok=True)
    log_path = os.path.join(canary_dir, f"{label}-watch.log")
    stream = open(log_path, "a")
    process = subprocess.Popen(
        [sys.executable, "-m", "canary.cli", "watch", watch_dir],
        stdin=subprocess.DEVNULL,
        stdout=stream,
        stderr=subprocess.STDOUT,
    )
    return WatchSidecar(process=process, stream=stream, log_path=log_path)


def _stop_watch_sidecar(sidecar: WatchSidecar | None) -> None:
    if sidecar is None:
        return

    if sidecar.process.poll() is None:
        sidecar.process.terminate()
        try:
            sidecar.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            sidecar.process.kill()
            sidecar.process.wait(timeout=3)

    sidecar.stream.close()


def _resolve_agent(binary_name: str) -> str:
    path = shutil.which(binary_name)
    if path:
        return path

    fail(f"{binary_name} not found", "install it or add it to your PATH")
    raise SystemExit(127)


def _mode_args(binary_name: str, mode: str) -> list[str]:
    if binary_name == "claude":
        return [] if mode == "interactive" else ["-p"]
    return []


def run_guarded_agent(
    *,
    binary_name: str,
    prompt: str,
    mode: str = "interactive",
    forwarded_args: list[str] | None = None,
    watch: bool = False,
    watch_dir: str = ".",
    binary_path: str | None = None,
    watch_label: str | None = None,
) -> int:
    forwarded_args = forwarded_args or []
    watch_dir = os.path.abspath(watch_dir)

    if watch and not os.path.isdir(watch_dir):
        console.print(f"  [red]watch dir not found[/red]  [dim]{watch_dir}[/dim]")
        return 2

    target = watch_dir if watch else os.getcwd()
    _run_prompt_gate(prompt, target)

    sidecar = None
    if watch:
        sidecar = _start_watch_sidecar(watch_dir, watch_label or f"{binary_name}-safe")
        note(f"watch log {os.path.relpath(sidecar.log_path, os.getcwd())}")
        console.print()

    agent_path = binary_path or _resolve_agent(binary_name)
    ok(f"launch {binary_name}", f"mode {mode}")
    console.print()
    try:
        result = subprocess.run([agent_path, *_mode_args(binary_name, mode), prompt, *forwarded_args])
        return result.returncode
    finally:
        _stop_watch_sidecar(sidecar)


def _run_wrapper(
    *,
    parser: argparse.ArgumentParser,
    argv: list[str] | None,
    binary_name: str,
    watch_label: str,
) -> int:
    ns = parser.parse_args(argv)
    forwarded = _normalize_forwarded_args(list(ns.agent_args))
    mode = "once" if ns.once else ns.mode
    return run_guarded_agent(
        binary_name=binary_name,
        prompt=ns.prompt,
        mode=mode,
        forwarded_args=forwarded,
        watch=ns.watch,
        watch_dir=ns.watch_dir,
        binary_path=None,
        watch_label=watch_label,
    )


def claude_safe(argv: list[str] | None = None) -> None:
    """gate a prompt, then run claude code."""
    parser = _build_parser("claude-safe", "gate a prompt, then run claude")
    raise SystemExit(_run_wrapper(
        parser=parser,
        argv=argv,
        binary_name="claude",
        watch_label="claude-safe",
    ))
