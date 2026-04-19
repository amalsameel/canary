"""Runtime entrypoint for direct claude/codex guard shims."""
from __future__ import annotations

import os
import subprocess
import sys

from .guard import load_guard_config
from .wrappers import run_guarded_agent

CODEX_SUBCOMMANDS = {
    "exec",
    "login",
    "logout",
    "help",
    "completion",
    "resume",
    "mcp",
    "config",
}


def parse_claude_args(argv: list[str]) -> tuple[str, str, list[str]] | None:
    if not argv:
        return None
    if argv[0] in {"-p", "--print"} and len(argv) >= 2:
        return "once", argv[1], argv[2:]
    if not argv[0].startswith("-"):
        return "interactive", argv[0], argv[1:]
    return None


def parse_codex_args(argv: list[str]) -> tuple[str, str, list[str]] | None:
    if not argv:
        return None
    if argv[0] == "exec" and len(argv) >= 2 and not argv[1].startswith("-"):
        return "once", argv[1], argv[2:]
    if not argv[0].startswith("-") and argv[0] not in CODEX_SUBCOMMANDS:
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

    parsed = parse_claude_args(argv) if agent == "claude" else parse_codex_args(argv)
    if parsed is None:
        return subprocess.run([real_binary, *argv]).returncode

    mode, prompt, forwarded = parsed
    return run_guarded_agent(
        binary_name=agent,
        prompt=prompt,
        mode=mode,
        forwarded_args=forwarded,
        watch=watch,
        watch_dir=watch_dir,
        binary_path=real_binary,
        watch_label=f"{agent}-guard",
    )


if __name__ == "__main__":
    raise SystemExit(main())
