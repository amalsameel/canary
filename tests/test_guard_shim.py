from canary.guard_shim import parse_claude_args, parse_codex_args


def test_parse_claude_interactive_prompt():
    assert parse_claude_args(["fix the login bug"]) == (
        "interactive",
        "fix the login bug",
        [],
    )


def test_parse_claude_print_prompt():
    assert parse_claude_args(["-p", "summarize this repo", "--model", "sonnet"]) == (
        "once",
        "summarize this repo",
        ["--model", "sonnet"],
    )


def test_parse_codex_exec_prompt():
    assert parse_codex_args(["exec", "review latest changes", "--json"]) == (
        "once",
        "review latest changes",
        ["--json"],
    )


def test_parse_codex_subcommand_without_prompt_passthrough():
    assert parse_codex_args(["login"]) is None
