# canary/config.py
"""Configuration management (local-only mode)."""
from pathlib import Path

CONFIG_DIR = Path.home() / ".canary"


def get_config_dir() -> Path:
    """Get or create config directory."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def get_screening_enabled() -> bool:
    """Check if screening is enabled (stored in simple flag file)."""
    flag_file = CONFIG_DIR / "screening_enabled"
    if flag_file.exists():
        return flag_file.read_text().strip().lower() == "true"
    return True  # Default on


def set_screening_enabled(enabled: bool) -> None:
    """Set screening enabled state."""
    get_config_dir()
    flag_file = CONFIG_DIR / "screening_enabled"
    flag_file.write_text("true" if enabled else "false")
