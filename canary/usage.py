"""Daily API usage tracking and soft limits for IBM online mode."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

_USAGE_PATH = Path.home() / ".canary" / "usage.json"

_KIND_LABELS = {
    "generate": "text generation",
    "embed":    "embeddings",
}


class LimitExceeded(Exception):
    def __init__(self, kind: str, used: int, limit: int) -> None:
        self.kind = kind
        self.used = used
        self.limit = limit
        super().__init__(f"{_KIND_LABELS.get(kind, kind)} daily limit reached ({used}/{limit})")


def get_limits() -> dict[str, int]:
    return {
        "generate": int(os.environ.get("CANARY_GENERATE_LIMIT", "100")),
        "embed":    int(os.environ.get("CANARY_EMBED_LIMIT",    "300")),
    }


def _today() -> str:
    return date.today().isoformat()


def _load() -> dict:
    try:
        if _USAGE_PATH.exists():
            data = json.loads(_USAGE_PATH.read_text())
            if data.get("date") == _today():
                return data
    except Exception:
        pass
    return {"date": _today(), "generate": 0, "embed": 0}


def _save(data: dict) -> None:
    try:
        _USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _USAGE_PATH.write_text(json.dumps(data))
    except Exception:
        pass


def get_usage() -> dict:
    data = _load()
    limits = get_limits()
    return {
        "date": data["date"],
        "generate": {"used": data.get("generate", 0), "limit": limits["generate"]},
        "embed":    {"used": data.get("embed",    0), "limit": limits["embed"]},
    }


def check_and_increment(kind: str) -> None:
    """Increment counter for *kind*; raises LimitExceeded if the daily cap is hit."""
    limits = get_limits()
    limit = limits.get(kind, 9999)
    data = _load()
    used = data.get(kind, 0)
    if used >= limit:
        raise LimitExceeded(kind, used, limit)
    data[kind] = used + 1
    _save(data)


def near_limit(kind: str, threshold: float = 0.8) -> bool:
    usage = get_usage()
    info = usage.get(kind, {})
    used, limit = info.get("used", 0), info.get("limit", 1)
    return (used / limit) >= threshold
