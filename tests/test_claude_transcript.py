from canary.claude_transcript import (
    flatten_tool_result_content,
    iter_bash_tool_uses,
    iter_tool_results,
    parse_timestamp,
    tool_result_state,
)


def test_parse_timestamp_supports_claude_z_suffix():
    ts = parse_timestamp("2026-04-19T09:06:37.187Z")
    assert isinstance(ts, float)
    assert ts > 0


def test_iter_bash_tool_uses_reads_assistant_tool_intents():
    entry = {
        "type": "assistant",
        "timestamp": "2026-04-19T09:06:37.187Z",
        "sessionId": "abc123",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_demo",
                    "name": "Bash",
                    "input": {"command": "npm test"},
                }
            ]
        },
    }

    results = iter_bash_tool_uses(entry)

    assert results == [{
        "tool_use_id": "toolu_demo",
        "command": "npm test",
        "timestamp": parse_timestamp("2026-04-19T09:06:37.187Z"),
        "session_id": "abc123",
    }]


def test_iter_tool_results_reads_tool_result_payloads():
    entry = {
        "type": "user",
        "timestamp": "2026-04-19T09:08:27.442Z",
        "sessionId": "abc123",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_demo",
                    "content": "Command completed successfully",
                }
            ]
        },
    }

    results = iter_tool_results(entry)

    assert results == [{
        "tool_use_id": "toolu_demo",
        "content": "Command completed successfully",
        "timestamp": parse_timestamp("2026-04-19T09:08:27.442Z"),
        "session_id": "abc123",
    }]


def test_flatten_tool_result_content_joins_nested_text_blocks():
    content = [
        {"type": "text", "text": "First line"},
        {"type": "text", "content": "Second line"},
    ]

    assert flatten_tool_result_content(content) == "First line\nSecond line"


def test_tool_result_state_detects_rejected_permission_messages():
    text = "The user doesn't want to proceed with this tool use. The tool use was rejected."
    assert tool_result_state(text) == "rejected"
    assert tool_result_state("PASS tests/auth.test.js") == "completed"
