"""Helpers for tailing Claude Code transcript JSONL files."""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path


CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


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


def iter_bash_tool_uses(entry: dict) -> list[dict]:
    """Extract Bash tool-use intents from an assistant transcript entry."""
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


def iter_tool_results(entry: dict) -> list[dict]:
    """Extract tool results from a user transcript entry."""
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
        })
    return results


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
