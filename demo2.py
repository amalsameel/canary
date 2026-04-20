#!/usr/bin/env python3
"""Canary accelerated walkthrough.

Shows canary in a styled walkthrough with a simulated Claude Code session that
emits real canary hook payloads and file edits.

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
from canary.ui import BRAND, command_bar, console, divider, hero, note, ok, result_panel, warn


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
    command_bar(display)
    result = _run(argv, env=env, cwd=cwd, input_text=input_text)
    if show_output and result.stdout:
        console.print(result.stdout.rstrip(), markup=False, highlight=False, soft_wrap=True)
        console.print()
    if result.stderr and result.returncode != 0:
        console.print(result.stderr.rstrip(), style="red", markup=False, highlight=False, soft_wrap=True)
        console.print()
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
        note("no audit events captured")
        return

    lines = ["[bold white]claude code tool calls intercepted by canary[/bold white]", ""]

    for ev in events:
        hook = ev.get("hook", "pre")
        tool = ev.get("tool", "?")
        risk = ev.get("risk", "SAFE")
        color = _RISK_COLORS.get(risk, "white")
        direction = "←" if hook == "post" else "→"

        detail = ev.get("command") or ev.get("file") or ""
        if len(detail) > 60:
            detail = detail[:57] + "..."

        row = f"[dim]{direction}[/dim]  [bold]{tool}[/bold]"
        if detail:
            row += f"  [dim]{detail}[/dim]"
        row += f"  [{color}]{risk}[/{color}]"
        lines.append(row)

        if hook == "pre" and ev.get("repercussions") and risk not in ("SAFE",):
            lines.append(f"   [dim]╰─ {ev['repercussions']}[/dim]")

    result_panel("\n".join(lines), padding=(1, 2))


def _show_changed_files(project_dir: Path) -> None:
    files = sorted(
        str(p.relative_to(project_dir))
        for p in project_dir.rglob("*")
        if p.is_file() and ".canary/checkpoints" not in str(p) and p.name != ".env"
    )
    if not files:
        return
    lines = ["[bold white]project files after the session[/bold white]", ""]
    lines.extend(f"[dim]{path}[/dim]" for path in files)
    result_panel("\n".join(lines), padding=(1, 2))


def _show_session_review(*, home_dir: Path, project_dir: Path, env: dict[str, str]) -> None:
    divider("session log")
    result = _exec_step(
        [str(CANARY_BIN), "log", "."],
        display="canary log .",
        env=env, cwd=project_dir,
        show_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("canary log failed")
    pause()

    divider("checkpoints")
    result = _exec_step(
        [str(CANARY_BIN), "checkpoints", "."],
        display="canary checkpoints .",
        env=env, cwd=project_dir,
        show_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("canary checkpoints failed")
    pause()

    divider("rollback")
    result = _exec_step(
        [str(CANARY_BIN), "rollback", "."],
        display="canary rollback .",
        env=env, cwd=project_dir,
        show_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("canary rollback failed")
    ok("workspace restored to pre-session state")
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
    hero(subtitle="accelerated walkthrough", path=str(project_dir))
    result_panel(
        "\n".join((
            "[dim]agent[/dim]      simulated claude code session",
            f"[dim]backend[/dim]    [bold {BRAND}]{backend_label}[/bold {BRAND}]",
            f"[dim]workspace[/dim]  [dim]{project_dir}[/dim]",
            f"[dim]binary[/dim]     [dim]{claude_bin}[/dim]",
            "",
            "[dim]press Enter to advance  ·  Ctrl-C to exit[/dim]",
        ))
    )
    pause()

    divider("setup")

    result = _exec_step(
        [str(CANARY_BIN), "guard", "install"],
        display="canary guard install",
        env=env, cwd=project_dir,
    )
    if result.returncode != 0:
        raise RuntimeError("guard install failed")
    ok("canary hooks registered in Claude Code settings.json")

    result = _exec_step(
        [str(CANARY_BIN), "on"],
        display="canary on",
        env=env, cwd=project_dir,
    )
    if result.returncode != 0:
        raise RuntimeError("canary on failed")
    ok("prompt screening enabled")
    pause()

    divider("prompt firewall")
    note("canary screens prompts before they reach claude code")

    result = _exec_step(
        [str(CANARY_BIN), "prompt",
         "my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ fix things", "--strict"],
        display='canary prompt "my key is sk-abc123... fix things" --strict',
        env=env, cwd=project_dir,
        show_output=True,
    )
    if result.returncode == 0:
        warn("expected non-zero exit", "prompt should have been blocked")
    else:
        ok(f"blocked  [exit {result.returncode}]  secret pattern detected in prompt")
    pause()

    divider("monitors")
    note("audit captures every tool call claude code makes via hooks")
    note("watch snapshots the repo continuously so you can roll back")

    result = _exec_step(
        [str(CANARY_BIN), "audit"],
        display="canary audit",
        env=env, cwd=project_dir,
    )
    if result.returncode != 0:
        raise RuntimeError("canary audit failed")
    ok("audit listener started")

    result = _exec_step(
        [str(CANARY_BIN), "watch", ".", "--continuous"],
        display="canary watch . --continuous",
        env=env, cwd=project_dir,
    )
    if result.returncode != 0:
        raise RuntimeError("canary watch failed")
    ok("file watcher started")
    pause()

    divider("claude code session")
    note("this walkthrough uses a simulated claude binary that emits real canary hook events")

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
    return temp_root, home_dir, project_dir, agent_bin, env, _backend_label(backend_env)


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

        divider("done")
        note(f"temp workspace: {temp_root}")
        if keep:
            note("files left on disk for inspection")
        console.print()

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
