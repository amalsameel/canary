"""Runtime entrypoint for direct Claude Code guard shim."""
from __future__ import annotations

import os
import subprocess
import sys

from .guard import get_enabled, load_guard_config
from .wrappers import run_guarded_agent

_IGNORE_FLAGS = {"-ignore", "--ignore"}
_SAFE_FLAGS = {"-safe", "--safe"}


def _extract_canary_flags(argv: list[str]) -> tuple[list[str], bool, bool]:
    """Strip -ignore / -safe from argv; return (clean_argv, has_ignore, has_safe)."""
    clean, has_ignore, has_safe = [], False, False
    for arg in argv:
        if arg in _IGNORE_FLAGS:
            has_ignore = True
        elif arg in _SAFE_FLAGS:
            has_safe = True
        else:
            clean.append(arg)
    return clean, has_ignore, has_safe


def parse_claude_args(argv: list[str]) -> tuple[str, str, list[str]] | None:
    if not argv:
        return None
    if argv[0] in {"-p", "--print"} and len(argv) >= 2:
        return "once", argv[1], argv[2:]
    if not argv[0].startswith("-"):
        return "interactive", argv[0], argv[1:]
    return None


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    agent = os.environ.get("CANARY_GUARD_AGENT")
    if not agent:
        raise SystemExit("CANARY_GUARD_AGENT is not set")

    config = load_guard_config().get("agents", {})
    if agent not in config:
        raise SystemExit(f"guard is not configured for {agent}")

    info = config[agent]
    real_binary = info["real_binary"]
    watch = bool(info.get("watch"))
    watch_dir = os.getcwd()

    argv, has_ignore, has_safe = _extract_canary_flags(argv)
    should_check = (get_enabled() or has_safe) and not has_ignore

    if not should_check:
        return subprocess.run([real_binary, *argv]).returncode

    parsed = parse_claude_args(argv)
    if parsed is None:
        return subprocess.run([real_binary, *argv]).returncode

    mode, prompt, forwarded = parsed
    return run_guarded_agent(
        binary_name="claude",
        prompt=prompt,
        mode=mode,
        forwarded_args=forwarded,
        watch=watch,
        watch_dir=watch_dir,
        binary_path=real_binary,
        watch_label="claude-guard",
    )


if __name__ == "__main__":
    raise SystemExit(main())
