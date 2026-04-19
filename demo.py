#!/usr/bin/env python3
"""Live Canary demo.

Default mode:
  uses a fake `claude` binary that emits real hook payloads and file edits

Real mode:
  uses the real installed Claude CLI in non-interactive `-p` mode

Examples:
  python demo.py
  AUTO=1 python demo.py
  AUTO=1 DELAY=0.8 python demo.py
  python demo.py --real-claude
  python demo.py --real-claude --keep-demo
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
    """Re-exec through the repo-local virtualenv when available."""
    if not PYTHON_BIN.exists():
        return
    if Path(sys.executable).resolve() == PYTHON_BIN.resolve():
        return
    os.execv(str(PYTHON_BIN), [str(PYTHON_BIN), str(Path(__file__).resolve()), *sys.argv[1:]])


_bootstrap_python()

from dotenv import dotenv_values
from rich.console import Console
from rich.panel import Panel

from canary.guard import resolve_real_binary


AUTO = os.environ.get("AUTO", "0") == "1"
DELAY = float(os.environ.get("DELAY", "1.8"))
KEEP_DEMO = os.environ.get("KEEP_DEMO", "0") == "1"
BRAND = "#ccff04"
DEFAULT_REAL_PROMPT = (
    "Read the existing Express demo project, then add JWT authentication middleware. "
    "Create src/auth/middleware.js, update routes/orders.js and routes/payments.js to require auth, "
    "update package.json if needed, run one lightweight verification command if helpful, "
    "and print a concise summary of what changed."
)

console = Console()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run the Canary demo")
    parser.add_argument(
        "--real-claude",
        action="store_true",
        help="use the real installed claude cli instead of the fake demo agent",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_REAL_PROMPT,
        help="prompt to send to claude in --real-claude mode",
    )
    parser.add_argument(
        "--keep-demo",
        action="store_true",
        help="keep the temp demo workspace after the run",
    )
    return parser.parse_args(argv)


def pause(secs: float | None = None) -> None:
    if AUTO:
        time.sleep(secs if secs is not None else DELAY)
    else:
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(0)


def wait(secs: float) -> None:
    time.sleep(secs)


def section(title: str, hint: str = "") -> None:
    console.print()
    console.rule(f"[dim]{title}[/dim]", style="dim")
    if hint:
        console.print(f"  [dim]{hint}[/dim]")
    console.print()
    pause(0.4 if AUTO else None)


def note(text: str) -> None:
    console.print(f"  [dim]·  {text}[/dim]")


def hero(title: str, body: str) -> None:
    console.print()
    console.print(
        Panel(
            f"[bold {BRAND}]{title}[/bold {BRAND}]\n\n{body}",
            border_style=BRAND,
            padding=(1, 3),
            expand=False,
        )
    )
    console.print()


def cmd(text: str, char_delay: float = 0.02) -> None:
    console.print(f"\n[bold {BRAND}]❯[/bold {BRAND}] ", end="")
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(char_delay)
    console.print()


def _require_demo_runtime() -> None:
    missing = [str(path) for path in (CANARY_BIN, PYTHON_BIN) if not path.exists()]
    if missing:
        raise SystemExit(
            "demo requires the repo-local virtualenv with `canary` installed.\n"
            f"missing: {', '.join(missing)}"
        )


def _load_backend_env() -> dict[str, str]:
    keys = (
        "IBM_API_KEY",
        "IBM_PROJECT_ID",
        "IBM_REGION",
        "IBM_LOCAL",
        "IBM_MOCK",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_MODEL",
    )
    values: dict[str, str] = {}
    env_path = ROOT / ".env"
    file_values = dotenv_values(env_path) if env_path.exists() else {}
    for key in keys:
        value = os.environ.get(key)
        if not value:
            raw = file_values.get(key)
            value = str(raw) if raw not in (None, "") else ""
        if value:
            values[key] = value
    return values


def _backend_label(values: dict[str, str]) -> str:
    if values.get("IBM_LOCAL", "").lower() == "true":
        return "local Granite"
    if values.get("IBM_MOCK", "").lower() == "true":
        return "mock Granite"
    if values.get("IBM_API_KEY") and values.get("IBM_PROJECT_ID"):
        return f"online IBM ({values.get('IBM_REGION', 'us-south')})"
    return "unconfigured"


def _base_env(
    home_dir: Path,
    real_bin_dir: Path | None,
    backend_env: dict[str, str],
    *,
    mock_default: bool,
) -> dict[str, str]:
    env = os.environ.copy()
    merged_backend = dict(backend_env)
    if mock_default:
        merged_backend.setdefault("IBM_MOCK", "true")
        merged_backend.setdefault("IBM_LOCAL", "false")

    env.update(
        {
            "HOME": str(home_dir),
            "PYTHONPYCACHEPREFIX": str(home_dir / ".pycache"),
        }
    )

    path_parts = [str(home_dir / ".canary" / "bin")]
    if real_bin_dir is not None:
        path_parts.append(str(real_bin_dir))
    path_parts.extend([str(VENV_BIN), env.get("PATH", "")])
    env["PATH"] = os.pathsep.join(path_parts)
    env.update(merged_backend)
    return env


def _write_demo_env(project_dir: Path, values: dict[str, str]) -> None:
    lines: list[str] = []
    for key in ("IBM_API_KEY", "IBM_PROJECT_ID", "IBM_REGION", "IBM_LOCAL", "IBM_MOCK"):
        if key in values:
            lines.append(f"{key}={values[key]}")
    if lines:
        (project_dir / ".env").write_text("\n".join(lines) + "\n")


def _write_demo_project(project_dir: Path, backend_env: dict[str, str]) -> None:
    (project_dir / "routes").mkdir(parents=True, exist_ok=True)
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    _write_demo_env(project_dir, backend_env)

    (project_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "demo-api-project",
                "private": True,
                "dependencies": {"express": "^4.21.0"},
            },
            indent=2,
        )
        + "\n"
    )

    (project_dir / "routes" / "orders.js").write_text(
        textwrap.dedent(
            """\
            const express = require("express");
            const router = express.Router();

            router.get("/orders", (req, res) => {
              res.json({ ok: true, orders: [] });
            });

            module.exports = router;
            """
        )
    )

    (project_dir / "routes" / "payments.js").write_text(
        textwrap.dedent(
            """\
            const express = require("express");
            const router = express.Router();

            router.post("/payments", (req, res) => {
              res.json({ ok: true, accepted: false });
            });

            module.exports = router;
            """
        )
    )


def _write_demo_agent(real_bin_dir: Path) -> Path:
    script = real_bin_dir / "claude"
    script.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            exec {PYTHON_BIN} -m canary.demo_fake_claude "$@"
            """
        )
    )
    script.chmod(0o755)
    return script


def _run(
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    input_text: str | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
    )


def _stream_command(
    argv: list[str],
    *,
    display: str,
    env: dict[str, str],
    cwd: Path,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd(display)
    result = _run(argv, env=env, cwd=cwd, input_text=input_text)
    if result.stdout:
        console.print(result.stdout.rstrip())
    if result.stderr:
        console.print(result.stderr.rstrip())
    console.print()
    return result


def _tail_text(path: Path, lines: int = 120) -> str:
    if not path.exists():
        return f"(missing) {path}"
    content = path.read_text(errors="ignore").splitlines()
    return "\n".join(content[-lines:])


def _assert_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode == 0:
        return
    raise RuntimeError(f"{label} failed with exit code {result.returncode}")


def _prepare_fake_environment() -> tuple[Path, Path, Path, Path, dict[str, str], str]:
    temp_root = Path(tempfile.mkdtemp(prefix="canary-live-demo-"))
    home_dir = temp_root / "home"
    project_dir = temp_root / "demo-project"
    real_bin_dir = temp_root / "real-bin"
    home_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    real_bin_dir.mkdir(parents=True, exist_ok=True)

    backend_env = {"IBM_MOCK": "true", "IBM_LOCAL": "false"}
    _write_demo_project(project_dir, backend_env)
    demo_agent = _write_demo_agent(real_bin_dir)
    env = _base_env(home_dir, real_bin_dir, backend_env, mock_default=True)
    return temp_root, home_dir, project_dir, demo_agent, env, "mock Granite"


def _prepare_real_environment() -> tuple[Path, Path, Path, Path, dict[str, str], str]:
    real_claude = resolve_real_binary("claude")
    if not real_claude:
        raise SystemExit("real demo requires `claude` on PATH")

    temp_root = Path(tempfile.mkdtemp(prefix="canary-real-demo-"))
    home_dir = temp_root / "home"
    project_dir = temp_root / "demo-project"
    home_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)

    user_claude_dir = Path.home() / ".claude"
    if user_claude_dir.exists():
        shutil.copytree(user_claude_dir, home_dir / ".claude", dirs_exist_ok=True)
    else:
        (home_dir / ".claude").mkdir(parents=True, exist_ok=True)

    backend_env = _load_backend_env()
    _write_demo_project(project_dir, backend_env)
    env = _base_env(home_dir, None, backend_env, mock_default=False)
    return temp_root, home_dir, project_dir, Path(real_claude), env, _backend_label(backend_env)


def _best_effort_stop(env: dict[str, str], cwd: Path) -> None:
    for args in ([str(CANARY_BIN), "audit", "--stop"], [str(CANARY_BIN), "watch", "--stop"]):
        try:
            _run(args, env=env, cwd=cwd)
        except Exception:
            pass


def _show_logs_and_restore(*, home_dir: Path, project_dir: Path, env: dict[str, str]) -> None:
    section("phase 6 · inspect the resulting logs", "these are the real background log files produced by canary audit/watch")
    audit_log = home_dir / ".canary" / "audit.log"
    watch_log = home_dir / ".canary" / "watch.log"
    hero("Audit Log", f"[dim]{audit_log}[/dim]\n\n{_tail_text(audit_log)}")
    pause()
    hero("Watch Log", f"[dim]{watch_log}[/dim]\n\n{_tail_text(watch_log)}")
    pause()

    section("phase 7 · inspect project state and checkpoints", "show the actual tracked session log and saved snapshots")
    result = _stream_command([str(CANARY_BIN), "log", "."], display="canary log .", env=env, cwd=project_dir)
    _assert_success(result, "canary log")
    result = _stream_command([str(CANARY_BIN), "checkpoints", "."], display="canary checkpoints .", env=env, cwd=project_dir)
    _assert_success(result, "canary checkpoints")
    pause()

    section("phase 8 · roll back", "restore the workspace from the automatic checkpoint created by canary watch")
    result = _stream_command([str(CANARY_BIN), "rollback", "."], display="canary rollback .", env=env, cwd=project_dir)
    _assert_success(result, "canary rollback")
    console.print("  [dim]current files after rollback:[/dim]")
    for rel in sorted(str(path.relative_to(project_dir)) for path in project_dir.rglob("*") if path.is_file() and ".canary/checkpoints" not in str(path)):
        console.print(f"  [dim]·[/dim]  {rel}")
    console.print()
    pause()


def _run_fake_demo(*, temp_root: Path, home_dir: Path, project_dir: Path, fake_claude: Path, env: dict[str, str], backend_label: str) -> None:
    hero(
        "Demo Workspace",
        "\n".join(
            [
                f"[dim]mode[/dim]     demo agent",
                f"[dim]backend[/dim]  {backend_label}",
                f"[dim]root[/dim]     {temp_root}",
                f"[dim]home[/dim]     {home_dir}",
                f"[dim]project[/dim]  {project_dir}",
                f"[dim]claude[/dim]   {fake_claude}",
            ]
        ),
    )

    section("phase 1 · install the guard", "use the real canary cli against an isolated demo agent binary")
    result = _stream_command([str(CANARY_BIN), "guard", "install"], display="canary guard install", env=env, cwd=project_dir)
    _assert_success(result, "guard install")
    pause()

    section("phase 2 · enable screening", "prompt screening toggles the installed claude shim")
    result = _stream_command([str(CANARY_BIN), "on"], display="canary on", env=env, cwd=project_dir)
    _assert_success(result, "canary on")
    pause()

    section("phase 3 · prompt firewall", "show a real blocked prompt before we start the agent session")
    result = _stream_command(
        [str(CANARY_BIN), "prompt", "my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ fix things", "--strict"],
        display='canary prompt "my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ fix things" --strict',
        env=env,
        cwd=project_dir,
    )
    note(f"expected non-zero exit for strict blocking  ·  exit {result.returncode}")
    console.print()
    pause()

    section("phase 4 · arm the background listeners", "audit captures hook activity and watch tracks the repo")
    result = _stream_command([str(CANARY_BIN), "audit"], display="canary audit", env=env, cwd=project_dir)
    _assert_success(result, "canary audit")
    result = _stream_command([str(CANARY_BIN), "watch", "."], display="canary watch .", env=env, cwd=project_dir)
    _assert_success(result, "canary watch")
    pause()

    section("phase 5 · run claude through the shim", "the demo agent binary emits real hook payloads and edits files")
    result = _stream_command(
        ["claude", "add JWT authentication middleware to the orders and payments routes"],
        display='claude "add JWT authentication middleware to the orders and payments routes"',
        env=env,
        cwd=project_dir,
        input_text="y\n",
    )
    _assert_success(result, "guarded claude session")
    wait(3.0)
    console.print()
    pause()

    _show_logs_and_restore(home_dir=home_dir, project_dir=project_dir, env=env)


def _run_real_demo(
    *,
    temp_root: Path,
    home_dir: Path,
    project_dir: Path,
    real_claude: Path,
    env: dict[str, str],
    backend_label: str,
    prompt: str,
) -> None:
    hero(
        "Demo Workspace",
        "\n".join(
            [
                f"[dim]mode[/dim]     real claude agent",
                f"[dim]backend[/dim]  {backend_label}",
                f"[dim]root[/dim]     {temp_root}",
                f"[dim]home[/dim]     {home_dir}",
                f"[dim]project[/dim]  {project_dir}",
                f"[dim]claude[/dim]   {real_claude}",
            ]
        ),
    )

    if backend_label == "unconfigured":
        hero(
            "Backend Warning",
            "[yellow]No Canary backend was found in env or repo `.env`.[/yellow]\n\n"
            "Prompt regex checks will still work, but semantic prompt scanning and drift detection may be incomplete.\n"
            "For a fuller demo, set `IBM_LOCAL=true` or export `IBM_API_KEY` and `IBM_PROJECT_ID` first.",
        )
        pause()

    section("phase 1 · install the guard", "install canary against the real claude binary inside an isolated temp home")
    result = _stream_command([str(CANARY_BIN), "guard", "install"], display="canary guard install", env=env, cwd=project_dir)
    _assert_success(result, "guard install")
    pause()

    section("phase 2 · enable screening", "prompt screening toggles the real claude shim")
    result = _stream_command([str(CANARY_BIN), "on"], display="canary on", env=env, cwd=project_dir)
    _assert_success(result, "canary on")
    pause()

    section("phase 3 · prompt firewall", "show a real blocked prompt before launching claude")
    result = _stream_command(
        [str(CANARY_BIN), "prompt", "my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ fix things", "--strict"],
        display='canary prompt "my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ fix things" --strict',
        env=env,
        cwd=project_dir,
    )
    note(f"expected non-zero exit for strict blocking  ·  exit {result.returncode}")
    console.print()
    pause()

    section("phase 4 · arm the background listeners", "audit listens for claude hook events and watch monitors the repo continuously")
    result = _stream_command([str(CANARY_BIN), "audit"], display="canary audit", env=env, cwd=project_dir)
    _assert_success(result, "canary audit")
    result = _stream_command([str(CANARY_BIN), "watch", ".", "--continuous"], display="canary watch . --continuous", env=env, cwd=project_dir)
    _assert_success(result, "canary watch")
    pause()

    section("phase 5 · run the real claude agent", "use claude print mode so the whole session can run end-to-end from one command")
    result = _stream_command(
        ["claude", "-p", prompt, "--permission-mode", "bypassPermissions"],
        display='claude -p "<demo prompt>" --permission-mode bypassPermissions',
        env=env,
        cwd=project_dir,
    )
    _assert_success(result, "real claude session")
    wait(3.0)
    console.print()
    pause()

    _show_logs_and_restore(home_dir=home_dir, project_dir=project_dir, env=env)


def main() -> None:
    _require_demo_runtime()
    args = _parse_args()
    keep_demo = KEEP_DEMO or args.keep_demo

    console.print()
    console.print(
        Panel(
            f"[bold {BRAND}]canary[/bold {BRAND}]  [dim]live demo[/dim]\n\n"
            f"  [dim]{'auto-advance  (AUTO=1)' if AUTO else 'press Enter to advance each step'}[/dim]\n"
            f"  [dim]uses the real canary cli in an isolated temp home/workspace[/dim]\n"
            f"  [dim]{'real claude mode' if args.real_claude else 'demo agent mode'}[/dim]\n"
            f"  [dim]Ctrl-C to exit at any time[/dim]",
            border_style=BRAND,
            padding=(1, 3),
            expand=False,
        )
    )
    console.print()

    if not AUTO:
        console.print("  [dim]press Enter to begin...[/dim]")
        pause()

    if args.real_claude:
        temp_root, home_dir, project_dir, claude_path, env, backend_label = _prepare_real_environment()
    else:
        temp_root, home_dir, project_dir, claude_path, env, backend_label = _prepare_fake_environment()

    try:
        if args.real_claude:
            _run_real_demo(
                temp_root=temp_root,
                home_dir=home_dir,
                project_dir=project_dir,
                real_claude=claude_path,
                env=env,
                backend_label=backend_label,
                prompt=args.prompt,
            )
        else:
            _run_fake_demo(
                temp_root=temp_root,
                home_dir=home_dir,
                project_dir=project_dir,
                fake_claude=claude_path,
                env=env,
                backend_label=backend_label,
            )

        hero(
            "Demo Complete",
            "\n".join(
                [
                    "[dim]this run exercised the real canary cli, guard shim, hooks, watcher, log, checkpoints, and rollback[/dim]",
                    f"[dim]claude mode[/dim]    {'real' if args.real_claude else 'demo'}",
                    f"[dim]temp demo root[/dim]  {temp_root}",
                    "[dim]set KEEP_DEMO=1 or pass --keep-demo to leave the temp workspace on disk for inspection[/dim]",
                ]
            ),
        )

    finally:
        _best_effort_stop(env, project_dir)
        if keep_demo:
            note(f"kept demo files at {temp_root}")
            console.print()
        else:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]demo interrupted[/dim]\n")
        raise SystemExit(0)
