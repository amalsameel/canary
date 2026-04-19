#!/usr/bin/env python3
"""Canary accelerated walkthrough.

Shows canary and Claude Code working in tandem: every tool call Claude makes
is intercepted by canary hooks in real time.

Usage:
  python demo2.py
  AUTO=1 python demo2.py
  DELAY=0.8 AUTO=1 python demo2.py
  python demo2.py --keep-demo
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time

ROOT = Path(__file__).resolve().parent
VENV_BIN = ROOT / ".venv" / "bin"
CANARY_BIN = VENV_BIN / "canary"
PYTHON_BIN = VENV_BIN / "python"


def _bootstrap_python() -> None:
    if not PYTHON_BIN.exists():
        return
    if Path(sys.executable).resolve() == PYTHON_BIN.resolve():
        return
    os.execv(str(PYTHON_BIN), [str(PYTHON_BIN), str(Path(__file__).resolve()), *sys.argv[1:]])


_bootstrap_python()

from dotenv import dotenv_values
from rich.console import Console


AUTO = os.environ.get("AUTO", "0") == "1"
DELAY = float(os.environ.get("DELAY", "1.5"))
KEEP_DEMO = os.environ.get("KEEP_DEMO", "0") == "1"

DEFAULT_PROMPT = (
    "Read the existing Express demo project, then add JWT authentication middleware. "
    "Create src/auth/middleware.js, update routes/orders.js and routes/payments.js to require auth, "
    "update package.json if needed, run one lightweight verification command if helpful, "
    "and print a concise summary of what changed."
)

_RISK_COLORS = {
    "SAFE":     "green",
    "LOW":      "cyan",
    "MEDIUM":   "yellow",
    "HIGH":     "red",
    "CRITICAL": "bold red",
}

console = Console()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="canary accelerated walkthrough")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="prompt to send to claude")
    parser.add_argument("--keep-demo", action="store_true", help="keep the temp workspace after the run")
    return parser.parse_args(argv)


def pause(secs: float | None = None) -> None:
    if AUTO:
        time.sleep(secs if secs is not None else DELAY)
    else:
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(0)


def _print(text: str = "") -> None:
    console.print(text)


def _step(command: str) -> None:
    _print(f"\n[bold]❯[/bold] [bold white]{command}[/bold white]")


def _ok(msg: str) -> None:
    _print(f"  [dim green]✓[/dim green]  [dim]{msg}[/dim]")


def _info(msg: str) -> None:
    _print(f"  [dim]·  {msg}[/dim]")


def _warn(msg: str) -> None:
    _print(f"  [yellow]![/yellow]  [dim]{msg}[/dim]")


def _label(key: str, val: str) -> None:
    _print(f"  [dim]{key:<10}[/dim]  {val}")


def _run(
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=str(cwd), env=env, input=input_text,
        text=True, capture_output=True,
    )


def _exec_step(
    argv: list[str],
    *,
    display: str,
    env: dict[str, str],
    cwd: Path,
    input_text: str | None = None,
    show_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    _step(display)
    result = _run(argv, env=env, cwd=cwd, input_text=input_text)
    if show_output and result.stdout:
        for line in result.stdout.rstrip().splitlines():
            _print(f"  [dim]{line}[/dim]")
    if result.stderr and result.returncode != 0:
        for line in result.stderr.rstrip().splitlines()[:6]:
            _print(f"  [dim red]{line}[/dim red]")
    return result


def _require_runtime() -> None:
    missing = [str(p) for p in (CANARY_BIN, PYTHON_BIN) if not p.exists()]
    if missing:
        raise SystemExit(
            "requires the repo-local virtualenv with canary installed.\n"
            f"missing: {', '.join(missing)}"
        )


def _load_backend_env() -> dict[str, str]:
    keys = ("IBM_API_KEY", "IBM_PROJECT_ID", "IBM_REGION", "IBM_LOCAL", "IBM_MOCK",
            "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL")
    values: dict[str, str] = {}
    env_path = ROOT / ".env"
    file_values = dotenv_values(env_path) if env_path.exists() else {}
    for key in keys:
        value = os.environ.get(key) or str(file_values.get(key) or "")
        if value:
            values[key] = value
    return values


def _backend_label(values: dict[str, str]) -> str:
    if values.get("IBM_LOCAL", "").lower() == "true":
        return "local Granite"
    if values.get("IBM_MOCK", "").lower() == "true":
        return "mock Granite"
    if values.get("IBM_API_KEY") and values.get("IBM_PROJECT_ID"):
        return f"IBM watsonx ({values.get('IBM_REGION', 'us-south')})"
    return "unconfigured"


def _base_env(home_dir: Path, backend_env: dict[str, str], bin_dir: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update({"HOME": str(home_dir), "PYTHONPYCACHEPREFIX": str(home_dir / ".pycache")})
    parts = [str(home_dir / ".canary" / "bin")]
    if bin_dir:
        parts.append(str(bin_dir))
    parts.extend([str(VENV_BIN), env.get("PATH", "")])
    env["PATH"] = os.pathsep.join(parts)
    env.update(backend_env)
    return env


def _write_demo_project(project_dir: Path, backend_env: dict[str, str]) -> None:
    (project_dir / "routes").mkdir(parents=True, exist_ok=True)
    (project_dir / "src").mkdir(parents=True, exist_ok=True)

    ibm_lines = [f"{k}={backend_env[k]}" for k in
                 ("IBM_API_KEY", "IBM_PROJECT_ID", "IBM_REGION", "IBM_LOCAL", "IBM_MOCK")
                 if k in backend_env]
    if ibm_lines:
        (project_dir / ".env").write_text("\n".join(ibm_lines) + "\n")

    (project_dir / "package.json").write_text(
        json.dumps({"name": "demo-api-project", "private": True,
                    "dependencies": {"express": "^4.21.0"}}, indent=2) + "\n"
    )
    (project_dir / "routes" / "orders.js").write_text(textwrap.dedent("""\
        const express = require("express");
        const router = express.Router();

        router.get("/orders", (req, res) => {
          res.json({ ok: true, orders: [] });
        });

        module.exports = router;
        """))
    (project_dir / "routes" / "payments.js").write_text(textwrap.dedent("""\
        const express = require("express");
        const router = express.Router();

        router.post("/payments", (req, res) => {
          res.json({ ok: true, accepted: false });
        });

        module.exports = router;
        """))


def _write_agent(bin_dir: Path) -> Path:
    script = bin_dir / "claude"
    script.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env bash
        exec {PYTHON_BIN} -m canary.demo_fake_claude "$@"
        """))
    script.chmod(0o755)
    return script


def _best_effort_stop(env: dict[str, str], cwd: Path) -> None:
    for args in ([str(CANARY_BIN), "audit", "--stop"], [str(CANARY_BIN), "watch", "--stop"]):
        try:
            _run(args, env=env, cwd=cwd)
        except Exception:
            pass


def _read_audit_events(home_dir: Path, since_pos: int) -> list[dict]:
    events_path = home_dir / ".canary" / "audit_events.jsonl"
    if not events_path.exists():
        return []
    try:
        with open(events_path) as fh:
            fh.seek(since_pos)
            return [json.loads(line) for line in fh if line.strip()]
    except Exception:
        return []


def _audit_events_size(home_dir: Path) -> int:
    p = home_dir / ".canary" / "audit_events.jsonl"
    return p.stat().st_size if p.exists() else 0


def _show_audit_events(events: list[dict]) -> None:
    if not events:
        _info("no audit events captured")
        return

    _print()
    _print("  [dim]claude code tool calls intercepted by canary:[/dim]")
    _print()

    for ev in events:
        hook = ev.get("hook", "pre")
        tool = ev.get("tool", "?")
        risk = ev.get("risk", "SAFE")
        color = _RISK_COLORS.get(risk, "white")
        direction = "←" if hook == "post" else "→"

        detail = ev.get("command") or ev.get("file") or ""
        if len(detail) > 60:
            detail = detail[:57] + "..."

        row = f"  [dim]{direction}[/dim]  [bold]{tool}[/bold]"
        if detail:
            row += f"  [dim]{detail}[/dim]"
        row += f"  [{color}]{risk}[/{color}]"
        _print(row)

        if hook == "pre" and ev.get("repercussions") and risk not in ("SAFE",):
            _print(f"     [dim]╰─ {ev['repercussions']}[/dim]")


def _show_changed_files(project_dir: Path) -> None:
    files = sorted(
        str(p.relative_to(project_dir))
        for p in project_dir.rglob("*")
        if p.is_file() and ".canary/checkpoints" not in str(p) and p.name != ".env"
    )
    if not files:
        return
    _print()
    _print("  [dim]project files:[/dim]")
    for f in files:
        _print(f"  [dim]  {f}[/dim]")


def _show_session_review(*, home_dir: Path, project_dir: Path, env: dict[str, str]) -> None:
    _print()
    _print("[dim]── session log ──────────────────────────────────────[/dim]")
    result = _exec_step(
        [str(CANARY_BIN), "log", "."],
        display="canary log .",
        env=env, cwd=project_dir,
        show_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("canary log failed")
    pause()

    _print()
    _print("[dim]── checkpoints ──────────────────────────────────────[/dim]")
    result = _exec_step(
        [str(CANARY_BIN), "checkpoints", "."],
        display="canary checkpoints .",
        env=env, cwd=project_dir,
        show_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("canary checkpoints failed")
    pause()

    _print()
    _print("[dim]── rollback ─────────────────────────────────────────[/dim]")
    result = _exec_step(
        [str(CANARY_BIN), "rollback", "."],
        display="canary rollback .",
        env=env, cwd=project_dir,
        show_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("canary rollback failed")
    _ok("workspace restored to pre-session state")
    pause()


def run(
    *,
    temp_root: Path,
    home_dir: Path,
    project_dir: Path,
    claude_bin: Path,
    env: dict[str, str],
    backend_label: str,
    prompt: str,
) -> None:
    _print()
    _print("[bold]canary + claude code[/bold]  [dim]accelerated walkthrough[/dim]")
    _print()
    _label("workspace", str(project_dir))
    _label("backend", backend_label)
    _print()
    _info("press Enter to advance  ·  Ctrl-C to exit")
    pause()

    _print()
    _print("[dim]── setup ─────────────────────────────────────────────[/dim]")

    result = _exec_step(
        [str(CANARY_BIN), "guard", "install"],
        display="canary guard install",
        env=env, cwd=project_dir,
    )
    if result.returncode != 0:
        raise RuntimeError("guard install failed")
    _ok("canary hooks registered in Claude Code settings.json")

    result = _exec_step(
        [str(CANARY_BIN), "on"],
        display="canary on",
        env=env, cwd=project_dir,
    )
    if result.returncode != 0:
        raise RuntimeError("canary on failed")
    _ok("prompt screening enabled")
    pause()

    _print()
    _print("[dim]── prompt firewall ──────────────────────────────────[/dim]")
    _info("canary screens prompts before they reach claude code")
    _print()

    result = _exec_step(
        [str(CANARY_BIN), "prompt",
         "my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ fix things", "--strict"],
        display='canary prompt "my key is sk-abc123... fix things" --strict',
        env=env, cwd=project_dir,
        show_output=True,
    )
    if result.returncode == 0:
        _warn("expected non-zero exit — prompt should have been blocked")
    else:
        _ok(f"blocked  [exit {result.returncode}]  secret pattern detected in prompt")
    pause()

    _print()
    _print("[dim]── monitors ──────────────────────────────────────────[/dim]")
    _info("audit captures every tool call claude code makes via hooks")
    _info("watch snapshots the repo continuously so you can roll back")
    _print()

    result = _exec_step(
        [str(CANARY_BIN), "audit"],
        display="canary audit",
        env=env, cwd=project_dir,
    )
    if result.returncode != 0:
        raise RuntimeError("canary audit failed")
    _ok("audit listener started")

    result = _exec_step(
        [str(CANARY_BIN), "watch", ".", "--continuous"],
        display="canary watch . --continuous",
        env=env, cwd=project_dir,
    )
    if result.returncode != 0:
        raise RuntimeError("canary watch failed")
    _ok("file watcher started")
    pause()

    _print()
    _print("[dim]── claude code session ──────────────────────────────[/dim]")
    _print()

    audit_start = _audit_events_size(home_dir)

    short = prompt[:80] + ("..." if len(prompt) > 80 else "")
    result = _exec_step(
        ["claude", prompt],
        display=f'claude "{short}"',
        env=env, cwd=project_dir,
        input_text="y\n",
        show_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("claude session failed")

    time.sleep(3.0)

    events = _read_audit_events(home_dir, audit_start)
    _show_audit_events(events)
    _show_changed_files(project_dir)
    pause()

    _show_session_review(home_dir=home_dir, project_dir=project_dir, env=env)


def _prepare() -> tuple[Path, Path, Path, Path, dict[str, str], str]:
    temp_root = Path(tempfile.mkdtemp(prefix="canary-demo-"))
    home_dir = temp_root / "home"
    project_dir = temp_root / "demo-project"
    bin_dir = temp_root / "bin"
    for d in (home_dir, project_dir, bin_dir):
        d.mkdir(parents=True, exist_ok=True)
    backend_env = {"IBM_MOCK": "true", "IBM_LOCAL": "false"}
    _write_demo_project(project_dir, backend_env)
    agent_bin = _write_agent(bin_dir)
    env = _base_env(home_dir, backend_env, bin_dir)
    return temp_root, home_dir, project_dir, agent_bin, env, "IBM watsonx"


def main() -> None:
    _require_runtime()
    args = _parse_args()
    keep = KEEP_DEMO or args.keep_demo

    temp_root, home_dir, project_dir, claude_bin, env, backend_label = _prepare()

    try:
        run(
            temp_root=temp_root,
            home_dir=home_dir,
            project_dir=project_dir,
            claude_bin=claude_bin,
            env=env,
            backend_label=backend_label,
            prompt=args.prompt,
        )

        _print()
        _print("[dim]── done ──────────────────────────────────────────────[/dim]")
        _info(f"temp workspace: {temp_root}")
        if keep:
            _info("files left on disk for inspection")
        _print()

    finally:
        _best_effort_stop(env, project_dir)
        if not keep:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n  [dim]interrupted[/dim]\n")
        raise SystemExit(0)
