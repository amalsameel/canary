"""Append-only session event log. Rotates at 10,000 events."""
import json
import os
import time

CANARY_DIR = ".canary"
SESSION_FILE = "session.json"
MAX_EVENTS = 10_000


def _session_path(target: str = ".") -> str:
    return os.path.join(target, CANARY_DIR, SESSION_FILE)


def _rotate_if_needed(path: str, events: list) -> list:
    if len(events) < MAX_EVENTS:
        return events
    ts = time.strftime("%Y%m%d_%H%M%S")
    rotated = path.replace(".json", f".{ts}.json")
    with open(rotated, "w") as f:
        json.dump(events, f, indent=2)
    return []


def log_event(event_type: str, data: dict, target: str = ".") -> None:
    cdir = os.path.join(target, CANARY_DIR)
    os.makedirs(cdir, exist_ok=True)
    path = _session_path(target)
    events: list[dict] = []
    if os.path.exists(path):
        try:
            with open(path) as f:
                events = json.load(f)
        except (json.JSONDecodeError, OSError):
            events = []
    events = _rotate_if_needed(path, events)
    events.append({"timestamp": time.time(), "type": event_type, **data})
    with open(path, "w") as f:
        json.dump(events, f, indent=2)


def read_log(target: str = ".") -> list[dict]:
    path = _session_path(target)
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
