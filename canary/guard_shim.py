"""Runtime entrypoint for direct guarded agent shims."""
from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
import sys

from .guard import get_enabled, load_guard_config
from .wrappers import run_guarded_argv

_IGNORE_FLAGS = {"-ignore", "--ignore"}
_SAFE_FLAGS = {"-safe", "--safe"}
_CODEX_TOP_LEVEL_SUBCOMMANDS = {
    "review",
    "login",
    "logout",
    "mcp",
    "marketplace",
    "mcp-server",
    "app-server",
    "app",
    "completion",
    "sandbox",
    "debug",
    "apply",
    "resume",
    "fork",
    "cloud",
    "exec-server",
    "features",
    "help",
}
_CODEX_EXEC_SUBCOMMANDS = {
    "resume",
    "review",
    "help",
}
_CODEX_VALUE_FLAGS = {
    "-c",
    "--config",
    "--enable",
    "--disable",
    "--remote",
    "--remote-auth-token-env",
    "-i",
    "--image",
    "-m",
    "--model",
    "--local-provider",
    "-p",
    "--profile",
    "-s",
    "--sandbox",
    "-a",
    "--ask-for-approval",
    "-C",
    "--cd",
    "--add-dir",
}
_CODEX_BOOL_FLAGS = {
    "--oss",
    "--full-auto",
    "--dangerously-bypass-approvals-and-sandbox",
    "--search",
    "--no-alt-screen",
    "-h",
    "--help",
    "-V",
    "--version",
}
_CODEX_EXEC_VALUE_FLAGS = {
    "-c",
    "--config",
    "--enable",
    "--disable",
    "-i",
    "--image",
    "-m",
    "--model",
    "--local-provider",
    "-p",
    "--profile",
    "-s",
    "--sandbox",
    "-C",
    "--cd",
    "--add-dir",
    "--output-schema",
    "--color",
    "-o",
    "--output-last-message",
}
_CODEX_EXEC_BOOL_FLAGS = {
    "--oss",
    "--full-auto",
    "--dangerously-bypass-approvals-and-sandbox",
    "--skip-git-repo-check",
    "--ephemeral",
    "--json",
    "-h",
    "--help",
    "-V",
    "--version",
}


@dataclass(frozen=True)
class ParsedInvocation:
    mode: str
    prompt: str
    forwarded_args: list[str]
    argv: list[str]


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


def parse_claude_args(argv: list[str]) -> ParsedInvocation | None:
    if not argv:
        return None
    if argv[0] in {"-p", "--print"} and len(argv) >= 2:
        return ParsedInvocation(mode="once", prompt=argv[1], forwarded_args=argv[2:], argv=argv)
    if not argv[0].startswith("-"):
        return ParsedInvocation(mode="interactive", prompt=argv[0], forwarded_args=argv[1:], argv=argv)
    return None


def _has_inline_value(arg: str, flags: set[str]) -> bool:
    return any(flag.startswith("--") and arg.startswith(f"{flag}=") for flag in flags)


def _parse_option_prompt(
    argv: list[str],
    *,
    mode: str,
    subcommands: set[str],
    value_flags: set[str],
    bool_flags: set[str],
) -> ParsedInvocation | None:
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--":
            if i + 1 >= len(argv):
                return None
            prompt = argv[i + 1]
            if prompt in subcommands:
                return None
            return ParsedInvocation(
                mode=mode,
                prompt=prompt,
                forwarded_args=argv[:i] + argv[i + 2:],
                argv=argv,
            )
        if arg in subcommands:
            return None
        if arg in value_flags:
            if i + 1 >= len(argv):
                return None
            i += 2
            continue
        if _has_inline_value(arg, value_flags) or arg in bool_flags:
            i += 1
            continue
        if arg.startswith("-"):
            return None
        return ParsedInvocation(
            mode=mode,
            prompt=arg,
            forwarded_args=argv[:i] + argv[i + 1:],
            argv=argv,
        )
    return None


def parse_codex_args(argv: list[str]) -> ParsedInvocation | None:
    if not argv:
        return None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--":
            if i + 1 >= len(argv):
                return None
            prompt = argv[i + 1]
            if prompt == "exec" or prompt in _CODEX_TOP_LEVEL_SUBCOMMANDS:
                return None
            return ParsedInvocation(
                mode="interactive",
                prompt=prompt,
                forwarded_args=argv[:i] + argv[i + 2:],
                argv=argv,
            )
        if arg == "exec":
            parsed = _parse_option_prompt(
                argv[i + 1:],
                mode="once",
                subcommands=_CODEX_EXEC_SUBCOMMANDS,
                value_flags=_CODEX_EXEC_VALUE_FLAGS,
                bool_flags=_CODEX_EXEC_BOOL_FLAGS,
            )
            if parsed is None:
                return None
            return ParsedInvocation(
                mode=parsed.mode,
                prompt=parsed.prompt,
                forwarded_args=argv[:i] + parsed.forwarded_args,
                argv=argv,
            )
        if arg in _CODEX_TOP_LEVEL_SUBCOMMANDS:
            return None
        if arg in _CODEX_VALUE_FLAGS:
            if i + 1 >= len(argv):
                return None
            i += 2
            continue
        if _has_inline_value(arg, _CODEX_VALUE_FLAGS) or arg in _CODEX_BOOL_FLAGS:
            i += 1
            continue
        if arg.startswith("-"):
            return None
        return ParsedInvocation(
            mode="interactive",
            prompt=arg,
            forwarded_args=argv[:i] + argv[i + 1:],
            argv=argv,
        )
    return None


def parse_agent_args(agent: str, argv: list[str]) -> ParsedInvocation | None:
    if agent == "claude":
        return parse_claude_args(argv)
    if agent == "codex":
        return parse_codex_args(argv)
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

    parsed = parse_agent_args(agent, argv)
    if parsed is None:
        return subprocess.run([real_binary, *argv]).returncode

    return run_guarded_argv(
        binary_name=agent,
        prompt=parsed.prompt,
        argv=parsed.argv,
        watch=watch,
        watch_dir=watch_dir,
        binary_path=real_binary,
        watch_label=f"{agent}-guard",
        launch_detail=f"mode {parsed.mode}",
    )


if __name__ == "__main__":
    raise SystemExit(main())
