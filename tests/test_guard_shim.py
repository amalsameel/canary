from canary.guard_shim import parse_claude_args


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
