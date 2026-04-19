"""Sensitive-file glob matching. Matches against the filename (not full path)."""
import fnmatch
import os

DEFAULT_SENSITIVE_PATTERNS = [
    ".env", ".env.*",
    "*.key", "*.pem", "*.p12", "*.pfx",
    "id_rsa", "id_ed25519", "id_dsa",
    "secrets.*", "credentials.*",
    "*password*", "*passwd*",
    "*token*", "*.secret",
    "*.keystore", "*.jks",
]


def is_sensitive(path: str, patterns: list[str] | None = None) -> bool:
    """Return True if the filename of `path` matches any sensitive glob pattern."""
    patterns = patterns if patterns is not None else DEFAULT_SENSITIVE_PATTERNS
    filename = os.path.basename(path)
    return any(fnmatch.fnmatch(filename, p) for p in patterns)
