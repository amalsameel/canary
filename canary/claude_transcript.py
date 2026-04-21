"""Helpers for tailing compatible Claude and Codex transcript JSONL files."""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path


CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
CODEX_SESSIONS_DIR = Path.home() / ".codex" / "sessions"


def parse_timestamp(value: str | None) -> float | None:
    """Convert a Claude transcript timestamp into a POSIX timestamp."""
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return _dt.datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None


def read_jsonl_since(path: str | Path, offset: int = 0, remainder: str = "") -> tuple[int, str, list[dict]]:
    """Read JSONL entries from *path* starting at *offset*.

    Returns `(new_offset, remainder, entries)` so callers can safely tail files
    while they are still being written to.
    """
    transcript_path = Path(path)
    if not transcript_path.exists():
        return offset, remainder, []

    with transcript_path.open("r", encoding="utf-8", errors="ignore") as handle:
        handle.seek(offset)
        chunk = handle.read()
        new_offset = handle.tell()

    data = remainder + chunk
    if not data:
        return new_offset, "", []

    lines = data.splitlines(keepends=True)
    if data and not data.endswith("\n"):
        remainder = lines.pop() if lines else data
    else:
        remainder = ""

    entries: list[dict] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return new_offset, remainder, entries


def _iter_claude_bash_tool_uses(entry: dict) -> list[dict]:
    if entry.get("type") != "assistant":
        return []

    message = entry.get("message", {})
    content = message.get("content", [])
    if not isinstance(content, list):
        return []

    results = []
    for item in content:
        if item.get("type") != "tool_use" or item.get("name") != "Bash":
            continue
        tool_input = item.get("input", {}) or {}
        command = str(tool_input.get("command", "")).strip()
        if not command:
            continue
        results.append({
            "tool_use_id": item.get("id", ""),
            "command": command,
            "timestamp": parse_timestamp(entry.get("timestamp")),
            "session_id": entry.get("sessionId", ""),
        })
    return results


def _iter_codex_exec_command_calls(entry: dict) -> list[dict]:
    if entry.get("type") != "response_item":
        return []

    payload = entry.get("payload", {})
    if not isinstance(payload, dict):
        return []
    if payload.get("type") != "function_call" or payload.get("name") != "exec_command":
        return []

    arguments = payload.get("arguments", "")
    if not isinstance(arguments, str):
        return []
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []

    command = str(parsed.get("cmd", "")).strip()
    if not command:
        return []

    return [{
        "tool_use_id": payload.get("call_id", ""),
        "command": command,
        "timestamp": parse_timestamp(entry.get("timestamp")),
        "session_id": "",
        "cwd": str(parsed.get("workdir", "") or ""),
    }]


def iter_bash_tool_uses(entry: dict) -> list[dict]:
    """Extract Bash/exec-command intents from compatible transcript entries."""
    return _iter_claude_bash_tool_uses(entry) + _iter_codex_exec_command_calls(entry)


def flatten_tool_result_content(content) -> str:
    """Convert Claude tool-result payloads into readable text."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
            continue
        nested = item.get("content")
        if isinstance(nested, str):
            parts.append(nested)
    return "\n".join(part for part in parts if part).strip()


def _iter_claude_tool_results(entry: dict) -> list[dict]:
    if entry.get("type") != "user":
        return []

    message = entry.get("message", {})
    content = message.get("content", [])
    if not isinstance(content, list):
        return []

    results = []
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "tool_result":
            continue
        results.append({
            "tool_use_id": item.get("tool_use_id", ""),
            "content": flatten_tool_result_content(item.get("content", "")),
            "timestamp": parse_timestamp(entry.get("timestamp")),
            "session_id": entry.get("sessionId", ""),
            "state": tool_result_state(flatten_tool_result_content(item.get("content", ""))),
        })
    return results


def _iter_codex_tool_results(entry: dict) -> list[dict]:
    if entry.get("type") != "event_msg":
        return []

    payload = entry.get("payload", {})
    if not isinstance(payload, dict) or payload.get("type") != "exec_command_end":
        return []

    command_parts = payload.get("command", [])
    command = ""
    if isinstance(command_parts, list) and command_parts:
        command = str(command_parts[-1]).strip()

    status = str(payload.get("status", "") or "").lower() or "completed"
    exit_code = payload.get("exit_code")

    return [{
        "tool_use_id": payload.get("call_id", ""),
        "content": str(payload.get("aggregated_output", "") or ""),
        "timestamp": parse_timestamp(entry.get("timestamp")),
        "session_id": "",
        "state": status,
        "exit_code": exit_code if isinstance(exit_code, int) else None,
        "command": command,
        "cwd": str(payload.get("cwd", "") or ""),
    }]


def iter_tool_results(entry: dict) -> list[dict]:
    """Extract tool results from compatible transcript entries."""
    return _iter_claude_tool_results(entry) + _iter_codex_tool_results(entry)


def tool_result_state(text: str) -> str:
    """Classify a tool-result payload into a simple execution state."""
    lowered = text.lower()
    if (
        "rejected" in lowered
        or "doesn't want to proceed" in lowered
        or "permission denied" in lowered
        or "was denied" in lowered
    ):
        return "rejected"
    return "completed"
