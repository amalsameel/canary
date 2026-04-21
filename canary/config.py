# canary/config.py
"""Configuration management (local-only mode)."""
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".canary"

# Default configuration for watcher
DEFAULT_CONFIG = {
    "ignore_dirs": {".git", ".canary", "node_modules", "__pycache__", ".venv", "venv", ".tox", ".pytest_cache"},
    "ignore_exts": {".pyc", ".pyo", ".so", ".dylib", ".dll", ".class", ".o", ".obj"},
    "sensitive_patterns": [
        "*.env*",
        "*password*",
        "*secret*",
        "*key*",
        "*.pem",
        "*.key",
        "id_rsa*",
        "id_ed25519*",
        "*.p12",
        "*.pfx",
        ".aws/credentials",
    ],
    "max_file_size_bytes": 1024 * 1024,  # 1MB
    "change_rate_window": 10,  # seconds
    "change_rate_limit": 50,  # max changes in window
    "drift_alert": 0.3,
    "drift_entry_point": 0.15,
    "entry_points": {"main.py", "app.py", "index.js", "server.js", "cli.py"},
}


def _configured_dir() -> Path:
    override = os.environ.get("CANARY_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return CONFIG_DIR


def get_config_dir() -> Path:
    """Get or create config directory.

    Falls back to a local workspace path when the home-directory config path
    is not writable in restricted environments.
    """
    config_dir = _configured_dir()
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        if os.access(config_dir, os.W_OK):
            return config_dir
    except PermissionError:
        pass

    fallback = Path.cwd() / ".canary_home"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_screening_enabled() -> bool:
    """Check if screening is enabled (stored in simple flag file)."""
    flag_file = get_config_dir() / "screening_enabled"
    if flag_file.exists():
        return flag_file.read_text().strip().lower() == "true"
    return True  # Default on


def set_screening_enabled(enabled: bool) -> None:
    """Set screening enabled state."""
    flag_file = get_config_dir() / "screening_enabled"
    try:
        flag_file.write_text("true" if enabled else "false")
    except PermissionError:
        fallback = Path.cwd() / ".canary_home"
        fallback.mkdir(parents=True, exist_ok=True)
        (fallback / "screening_enabled").write_text("true" if enabled else "false")


def load_config(target: str) -> dict:
    """Load configuration for watching a target directory.

    Returns default configuration. In the future, could load from
    .canary/config.yaml in the target directory.
    """
    return DEFAULT_CONFIG.copy()
