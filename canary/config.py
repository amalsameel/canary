"""Load .canary.toml from the watched directory, falling back to built-in defaults.

Python 3.11+ has tomllib built in. We shim for 3.10 via tomli if present.
"""
import os

try:
    import tomllib  # py 3.11+
except ModuleNotFoundError:  # py 3.10
    import tomli as tomllib  # type: ignore

from .sensitive_files import DEFAULT_SENSITIVE_PATTERNS

DEFAULTS = {
    "drift_alert": 0.15,
    "drift_entry_point": 0.08,
    "change_rate_window": 60,
    "change_rate_limit": 10,
    "max_file_size_bytes": 512 * 1024,
    "entry_points": {"main.py", "app.py", "index.ts", "index.js", "server.py", "__init__.py"},
    "ignore_dirs": {".git", ".canary", "node_modules", "__pycache__", "venv", ".venv", "dist", "build", ".next", ".mypy_cache", ".pytest_cache"},
    "ignore_exts": {".pyc", ".so", ".dll", ".dylib", ".exe", ".bin", ".zip", ".tar", ".gz",
                    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".webp", ".mp3", ".mp4",
                    ".woff", ".woff2", ".ttf", ".otf"},
    "sensitive_patterns": list(DEFAULT_SENSITIVE_PATTERNS),
}


def load_config(target: str = ".") -> dict:
    """Return a config dict merging .canary.toml (if present) over DEFAULTS."""
    cfg: dict = {
        **DEFAULTS,
        "entry_points": set(DEFAULTS["entry_points"]),
        "ignore_dirs": set(DEFAULTS["ignore_dirs"]),
        "ignore_exts": set(DEFAULTS["ignore_exts"]),
        "sensitive_patterns": list(DEFAULTS["sensitive_patterns"]),
    }
    path = os.path.join(target, ".canary.toml")
    if not os.path.exists(path):
        return cfg
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return cfg

    th = data.get("thresholds", {})
    cfg["drift_alert"] = float(th.get("drift_alert", cfg["drift_alert"]))
    cfg["drift_entry_point"] = float(th.get("drift_entry_point", cfg["drift_entry_point"]))
    cfg["change_rate_window"] = int(th.get("change_rate_window", cfg["change_rate_window"]))
    cfg["change_rate_limit"] = int(th.get("change_rate_limit", cfg["change_rate_limit"]))
    cfg["max_file_size_bytes"] = int(th.get("max_file_size_bytes", cfg["max_file_size_bytes"]))

    ep = data.get("entry_points", {})
    if "files" in ep:
        cfg["entry_points"] = set(ep["files"])

    ig = data.get("ignore", {})
    if "dirs" in ig:
        cfg["ignore_dirs"] = set(ig["dirs"])
    if "extensions" in ig:
        cfg["ignore_exts"] = set(ig["extensions"])

    sen = data.get("sensitive", {})
    if "patterns" in sen:
        cfg["sensitive_patterns"] = list(sen["patterns"])

    return cfg
