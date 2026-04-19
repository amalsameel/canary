"""Crude but fast binary-file detection: look for null bytes in the first 1 KB."""
import os


def looks_binary(path: str, probe_bytes: int = 1024) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(probe_bytes)
    except OSError:
        return True
    if not chunk:
        return False
    return b"\x00" in chunk
