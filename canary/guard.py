"""Direct CLI guardrail integration for Claude Code and Codex."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import shlex
import stat
import sys


CONFIG_DIR = Path.home() / ".canary"
CONFIG_PATH = CONFIG_DIR / "guard.json"
DEFAULT_SHIM_DIR = CONFIG_DIR / "bin"


@dataclass
class GuardRecord:
    real_binary: str
    shim_path: str
    watch: bool


def _ensure_dirs(shim_dir: Path) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    shim_dir.mkdir(parents=True, exist_ok=True)


def load_guard_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"agents": {}}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {"agents": {}}


def save_guard_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def resolve_real_binary(agent: str, *, shim_dir: Path | None = None) -> str | None:
    shim_dir = (shim_dir or DEFAULT_SHIM_DIR).resolve()
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        entry_path = Path(entry).expanduser().resolve()
        if entry_path == shim_dir:
            continue
        candidate = entry_path / agent
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(agent)


def install_guard(agent: str, *, watch: bool = False, shim_dir: Path | None = None) -> GuardRecord:
    shim_dir = shim_dir or DEFAULT_SHIM_DIR
    _ensure_dirs(shim_dir)
    real_binary = resolve_real_binary(agent, shim_dir=shim_dir)
    if not real_binary:
        raise RuntimeError(f"could not find `{agent}` in PATH")

    shim_path = shim_dir / agent
    script = "\n".join((
        "#!/usr/bin/env bash",
        f"export CANARY_GUARD_AGENT={shlex.quote(agent)}",
        f"exec {shlex.quote(sys.executable)} -m canary.guard_shim \"$@\"",
        "",
    ))
    shim_path.write_text(script)
    shim_path.chmod(shim_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    config = load_guard_config()
    config.setdefault("agents", {})
    config["agents"][agent] = {
        "real_binary": real_binary,
        "shim_path": str(shim_path),
        "watch": watch,
    }
    save_guard_config(config)
    return GuardRecord(real_binary=real_binary, shim_path=str(shim_path), watch=watch)


def remove_guard(agent: str) -> None:
    config = load_guard_config()
    info = config.get("agents", {}).pop(agent, None)
    if info and info.get("shim_path"):
        try:
            Path(info["shim_path"]).unlink()
        except FileNotFoundError:
            pass
    save_guard_config(config)


def guard_records() -> dict[str, GuardRecord]:
    config = load_guard_config()
    records = {}
    for agent, info in config.get("agents", {}).items():
        records[agent] = GuardRecord(
            real_binary=info.get("real_binary", ""),
            shim_path=info.get("shim_path", ""),
            watch=bool(info.get("watch")),
        )
    return records
