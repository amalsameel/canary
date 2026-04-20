import canary.guard_shim as guard_shim
from canary.guard_shim import ParsedInvocation, parse_agent_args, parse_claude_args, parse_codex_args


def test_parse_claude_interactive_prompt():
    assert parse_claude_args(["fix the login bug"]) == ParsedInvocation(
        mode="interactive",
        prompt="fix the login bug",
        forwarded_args=[],
        argv=["fix the login bug"],
    )


def test_parse_claude_print_prompt():
    assert parse_claude_args(["-p", "summarize this repo", "--model", "sonnet"]) == ParsedInvocation(
        mode="once",
        prompt="summarize this repo",
        forwarded_args=["--model", "sonnet"],
        argv=["-p", "summarize this repo", "--model", "sonnet"],
    )


def test_parse_codex_interactive_prompt():
    assert parse_codex_args(["fix the login bug"]) == ParsedInvocation(
        mode="interactive",
        prompt="fix the login bug",
        forwarded_args=[],
        argv=["fix the login bug"],
    )


def test_parse_codex_interactive_prompt_after_options():
    assert parse_codex_args(["-m", "gpt-5", "--search", "fix the login bug"]) == ParsedInvocation(
        mode="interactive",
        prompt="fix the login bug",
        forwarded_args=["-m", "gpt-5", "--search"],
        argv=["-m", "gpt-5", "--search", "fix the login bug"],
    )


def test_parse_codex_exec_prompt():
    assert parse_codex_args(["exec", "-m", "gpt-5", "summarize this repo"]) == ParsedInvocation(
        mode="once",
        prompt="summarize this repo",
        forwarded_args=["-m", "gpt-5"],
        argv=["exec", "-m", "gpt-5", "summarize this repo"],
    )


def test_parse_codex_exec_prompt_after_global_options():
    assert parse_codex_args(["--profile", "fast", "exec", "-m", "gpt-5", "summarize this repo"]) == ParsedInvocation(
        mode="once",
        prompt="summarize this repo",
        forwarded_args=["--profile", "fast", "-m", "gpt-5"],
        argv=["--profile", "fast", "exec", "-m", "gpt-5", "summarize this repo"],
    )


def test_parse_codex_subcommand_returns_none():
    assert parse_codex_args(["review"]) is None


def test_parse_agent_args_dispatches_codex():
    parsed = parse_agent_args("codex", ["--search", "fix the login bug"])
    assert parsed is not None
    assert parsed.prompt == "fix the login bug"
    assert parsed.mode == "interactive"


def test_main_routes_codex_through_generic_guard(monkeypatch):
    monkeypatch.setenv("CANARY_GUARD_AGENT", "codex")
    monkeypatch.setattr(guard_shim, "load_guard_config", lambda: {
        "agents": {"codex": {"real_binary": "/opt/homebrew/bin/codex", "watch": True}},
    })
    monkeypatch.setattr(guard_shim, "get_enabled", lambda: True)

    captured = {}

    def fake_run_guarded_argv(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(guard_shim, "run_guarded_argv", fake_run_guarded_argv)

    assert guard_shim.main(["--search", "fix the login bug"]) == 0
    assert captured["binary_name"] == "codex"
    assert captured["prompt"] == "fix the login bug"
    assert captured["argv"] == ["--search", "fix the login bug"]
    assert captured["watch"] is True
