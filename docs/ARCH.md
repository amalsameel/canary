# canary — Architecture Document

**Version:** 0.3.0
**Last updated:** 2026-04-18

This document is the single source of truth for the canary codebase. Every code block below is meant to be copied **verbatim** into the corresponding file. Section numbers are stable — do not renumber.

---

## 1. System Overview

```
                        ┌─────────────────────────────┐
                        │         HUMAN               │
                        │   types a prompt            │
                        └──────────────┬──────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │   canary prompt <text>      │  ← Prompt Firewall
                        │   - secret detection        │
                        │   - PII detection (+Luhn)   │
                        │   - entropy analysis        │
                        │   - risk score bar          │
                        │   - --strict mode           │
                        └──────────────┬──────────────┘
                                       │ confirmed safe
                                       ▼
                        ┌─────────────────────────────┐
                        │       AI CODING AGENT       │
                        │  (Claude Code, Cursor, etc) │
                        └──────────────┬──────────────┘
                                       │ writes files
                                       ▼
                        ┌─────────────────────────────┐
                        │   canary watch ./src        │  ← File Watchdog
                        │   - inotify / FSEvents      │
                        │   - debouncing              │
                        │   - IBM Granite embeddings  │
                        │   - drift detection         │
                        │   - sensitive file guard    │
                        │   - checkpoint / rollback   │
                        │   - live risk score bar     │
                        └─────────────────────────────┘
```

---

## 2. Project Structure

```
canary/
├── canary/
│   ├── __init__.py             # __version__ = "0.1.0"
│   ├── cli.py                  # Click CLI entrypoint
│   ├── config.py               # .canary.toml loader + defaults
│   ├── prompt_firewall.py      # Prompt scanning (secrets, PII, entropy, Luhn)
│   ├── watcher.py              # Filesystem watchdog with debouncing
│   ├── drift.py                # Cosine similarity
│   ├── checkpoint.py           # Checkpoint creation and rollback
│   ├── risk.py                 # Risk score computation + progress bar
│   ├── sensitive_files.py      # Sensitive file glob matching
│   ├── session.py              # Session log read/write with rotation
│   ├── binary.py               # Binary-file detection
│   ├── mock.py                 # Mock IBM responses (deterministic)
│   └── ibm/
│       ├── __init__.py
│       ├── iam.py              # IBM IAM token refresh
│       └── embeddings.py       # Granite embedding call + sha256 cache
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── safe_prompt.txt
│   │   ├── leaky_prompt.txt
│   │   └── sample_project/
│   │       ├── main.py
│   │       ├── auth.py
│   │       └── .env
│   ├── test_firewall.py
│   ├── test_drift.py
│   └── test_sensitive_files.py
├── .env.example
├── .canary.toml.example
├── .gitignore
├── requirements.txt
├── setup.py
├── pyproject.toml
├── README.md
└── docs/
    ├── PRD.md
    ├── ARCH.md
    ├── README.md
    ├── CHANGELOG.md
    └── MASTERPROMPT.md
```

---

## 3. IBM Granite Integration

### §3.1 IAM Token (`canary/ibm/iam.py`)

```python
"""IBM Cloud IAM token acquisition with in-memory caching.

Tokens are valid for ~1 hour. We refresh 60 s before expiry to avoid edge-case 401s.
"""
import time
import os
import requests

_token_cache = {"token": None, "expires_at": 0.0}


def get_iam_token() -> str:
    """Return a valid IBM IAM bearer token, refreshing if needed."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    api_key = os.environ.get("IBM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "IBM_API_KEY not set. Either export it, put it in .env, or set IBM_MOCK=true."
        )

    resp = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    return _token_cache["token"]
```

### §3.2 Granite Embedding (`canary/ibm/embeddings.py`)

```python
"""IBM Granite embedding call with sha256 cache and region selection."""
import hashlib
import os
import requests

from .iam import get_iam_token
from ..mock import IBM_MOCK, mock_embedding

# In-memory cache: sha256(content) -> embedding vector
_cache: dict[str, list[float]] = {}

REGION_HOSTS = {
    "us-south": "us-south.ml.cloud.ibm.com",
    "eu-de":    "eu-de.ml.cloud.ibm.com",
    "jp-tok":   "jp-tok.ml.cloud.ibm.com",
    "eu-gb":    "eu-gb.ml.cloud.ibm.com",
    "au-syd":   "au-syd.ml.cloud.ibm.com",
}

MODEL_ID = "ibm/granite-embedding-278m-multilingual"
MAX_INPUT_CHARS = 8000  # Granite has a token cap; 8k chars is safely under it


def _endpoint() -> str:
    region = os.environ.get("IBM_REGION", "us-south").strip() or "us-south"
    host = REGION_HOSTS.get(region, REGION_HOSTS["us-south"])
    return f"https://{host}/ml/v1/text/embeddings?version=2024-05-31"


def get_embedding(text: str) -> list[float]:
    """Return a 768-dim embedding for `text`, cached by sha256."""
    key = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    if key in _cache:
        return _cache[key]
    if IBM_MOCK:
        vec = mock_embedding(key)
        _cache[key] = vec
        return vec

    project_id = os.environ.get("IBM_PROJECT_ID")
    if not project_id:
        raise RuntimeError(
            "IBM_PROJECT_ID not set. Either export it, put it in .env, or set IBM_MOCK=true."
        )

    token = get_iam_token()
    resp = requests.post(
        _endpoint(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "model_id": MODEL_ID,
            "project_id": project_id,
            "inputs": [text[:MAX_INPUT_CHARS]],
        },
        timeout=30,
    )
    resp.raise_for_status()
    vector = resp.json()["results"][0]["embedding"]
    _cache[key] = vector
    return vector
```

---

## 4. Prompt Firewall (`canary/prompt_firewall.py`)

```python
"""Prompt firewall: regex + entropy + Luhn secret & PII detection.

Returns a list of PromptFinding objects. Each finding carries the matched text
(used only for redacted display — never logged raw).
"""
import re
import math
import string
from dataclasses import dataclass


@dataclass
class PromptFinding:
    kind: str            # secret | pii | path | entropy
    severity: str        # CRITICAL | HIGH | MEDIUM
    description: str
    matched: str         # raw matched text; redacted before display
    score: int           # risk points


# ---------------------------------------------------------------------------
# Known-format secrets. Order matters: most specific first.
# ---------------------------------------------------------------------------
SECRET_PATTERNS: list[tuple[str, str, str, int]] = [
    (r'sk-[A-Za-z0-9_\-]{20,}',              'OpenAI / Anthropic API key',         'CRITICAL', 40),
    (r'ghp_[A-Za-z0-9]{30,40}',              'GitHub personal access token',       'CRITICAL', 40),
    (r'gh[osu]_[A-Za-z0-9]{30,40}',          'GitHub OAuth/server/user token',     'CRITICAL', 40),
    (r'glpat-[A-Za-z0-9_\-]{20,}',           'GitLab personal access token',       'CRITICAL', 40),
    (r'xox[baprs]-[A-Za-z0-9\-]{10,}',       'Slack token',                        'CRITICAL', 40),
    (r'AKIA[0-9A-Z]{16}',                    'AWS access key ID',                  'CRITICAL', 40),
    (r'AIza[0-9A-Za-z_\-]{35}',              'Google API key',                     'CRITICAL', 40),
    (r'hf_[A-Za-z0-9]{30,}',                 'Hugging Face token',                 'CRITICAL', 40),
    (r'(rk|sk|pk)_live_[A-Za-z0-9]{20,}',    'Stripe live key',                    'CRITICAL', 40),
    (r'(?i)(password|passwd|pwd)\s*[=:]\s*\S{6,}',     'Inline password assignment', 'HIGH', 30),
    (r'(?i)(secret|api[_-]?key|token)\s*[=:]\s*\S{8,}', 'Inline secret assignment',  'HIGH', 30),
]

# ---------------------------------------------------------------------------
# PII patterns.
# ---------------------------------------------------------------------------
PII_PATTERNS: list[tuple[str, str, str, int]] = [
    (r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', 'Email address',    'MEDIUM', 20),
    (r'\b\d{3}-\d{2}-\d{4}\b',                          'SSN',              'CRITICAL', 40),
    (r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b',                'Phone number',     'MEDIUM', 10),
]

# Credit card candidates (pre-Luhn): 13–19 digits with optional separators.
CC_CANDIDATE = re.compile(r'\b(?:\d[ -]?){12,18}\d\b')

# ---------------------------------------------------------------------------
# Sensitive path references.
# ---------------------------------------------------------------------------
PATH_PATTERNS: list[tuple[str, str, str, int]] = [
    (r'/etc/passwd',            'System password file path',   'HIGH',     25),
    (r'/etc/shadow',            'System shadow file path',     'CRITICAL', 40),
    (r'~/\.ssh/',               'SSH directory path',          'HIGH',     25),
    (r'(?<![A-Za-z0-9_])\.env(?![A-Za-z0-9_])', '.env file reference',     'HIGH', 25),
    (r'\bid_(?:rsa|ed25519|dsa)\b', 'Private key file reference', 'CRITICAL', 40),
    (r'/root/',                 'Root home directory path',    'MEDIUM',   15),
]

# Entropy-check allowlist: strings matching these are NOT flagged as entropy secrets.
ENTROPY_ALLOW = [
    re.compile(r'^[0-9a-f]{40}$'),                    # git SHA-1
    re.compile(r'^[0-9a-f]{64}$'),                    # SHA-256
    re.compile(r'^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$'),  # UUID
    re.compile(r'^sha(?:256|512):[0-9a-f]+$'),        # hash with prefix
]


def shannon_entropy(s: str) -> float:
    """Shannon entropy of a string in bits per character."""
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    length = len(s)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def luhn_valid(number: str) -> bool:
    """Luhn checksum for credit-card candidates. Digits only."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _is_allowed_entropy(token: str) -> bool:
    return any(r.match(token) for r in ENTROPY_ALLOW)


def scan_prompt(text: str) -> list[PromptFinding]:
    findings: list[PromptFinding] = []
    seen_spans: set[tuple[int, int]] = set()

    def _add(kind, severity, description, match_text, score, span):
        # Avoid double-counting the same span
        if span in seen_spans:
            return
        seen_spans.add(span)
        findings.append(PromptFinding(kind, severity, description, match_text, score))

    for pattern, description, severity, score in SECRET_PATTERNS:
        for m in re.finditer(pattern, text):
            _add("secret", severity, description, m.group(), score, m.span())

    for pattern, description, severity, score in PII_PATTERNS:
        for m in re.finditer(pattern, text):
            _add("pii", severity, description, m.group(), score, m.span())

    # Credit card: regex + Luhn
    for m in CC_CANDIDATE.finditer(text):
        raw = m.group()
        if luhn_valid(raw):
            _add("pii", "HIGH", "Credit card number (Luhn-valid)", raw, 30, m.span())

    for pattern, description, severity, score in PATH_PATTERNS:
        for m in re.finditer(pattern, text):
            _add("path", severity, description, m.group(), score, m.span())

    # Entropy sweep on whitespace-separated tokens
    for m in re.finditer(r'\S+', text):
        token = m.group().strip(string.punctuation)
        if len(token) < 20 or len(token) > 200:
            continue
        if _is_allowed_entropy(token):
            continue
        if shannon_entropy(token) > 4.5:
            if not any(f.matched == token for f in findings):
                _add("entropy", "HIGH",
                     "High-entropy string (possible secret)",
                     token, 25, m.span())

    return findings
```

---

## 5. Risk Score and Progress Bar (`canary/risk.py`)

```python
"""Risk scoring + colored progress bar rendering."""
from rich.console import Console

console = Console()


def compute_risk_score(findings: list) -> int:
    """Clamp total finding score to 0..100."""
    return min(sum(f.score for f in findings), 100)


def bar_color(score: int) -> str:
    if score <= 30:
        return "green"
    if score <= 60:
        return "yellow"
    return "red"


def render_risk_bar(score: int, label: str = "Risk Score") -> None:
    """Render a 20-block colored progress bar with percentage."""
    score = max(0, min(100, int(score)))
    color = bar_color(score)
    filled = round(score / 5)  # 100 / 5 = 20 blocks max
    filled = max(0, min(20, filled))
    empty = 20 - filled
    bar = "█" * filled + "░" * empty
    prefix = f"{label}: " if label else ""
    console.print(f"{prefix}[{color}][{bar}] {score}%[/{color}]")


def _redact(s: str) -> str:
    """Redact a matched string for display. Show only first 2 + last 2 chars."""
    if len(s) <= 6:
        return "***"
    return f"{s[:2]}***{s[-2:]}"


def render_findings(findings: list, score: int) -> None:
    if not findings:
        console.print("[green]✓ No sensitive data detected[/green]")
        render_risk_bar(score)
        return

    console.print()
    for f in findings:
        color = {"CRITICAL": "bold red", "HIGH": "red", "MEDIUM": "yellow"}.get(f.severity, "white")
        console.print(
            f"  [{color}][{f.severity}][/{color}] {f.description} — "
            f"[dim]{_redact(f.matched)}[/dim]"
        )
    console.print()
    render_risk_bar(score)
```

---

## 6. Filesystem Watchdog (`canary/watcher.py`)

```python
"""Filesystem watchdog with debouncing, binary-file skipping, and ignore patterns.

Critical design choices:
- `.canary/` is explicitly ignored; otherwise the session.json writes would
  trigger an infinite loop of on_modified events.
- Sensitive-pattern files are never embedded — their contents never leave the
  machine — but their access is logged and the user is prompted.
- Debounce: same path inside 300 ms is treated as a single event.
- Binary files and files > 512 KB are skipped.
"""
import os
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from rich.console import Console

from .ibm.embeddings import get_embedding
from .drift import cosine_similarity
from .sensitive_files import is_sensitive
from .checkpoint import take_snapshot
from .session import log_event
from .risk import render_risk_bar
from .binary import looks_binary
from .config import load_config

console = Console()


class CanaryHandler(FileSystemEventHandler):
    def __init__(self, baseline: dict[str, list[float]], cfg: dict, target: str):
        self.baseline = baseline
        self.cfg = cfg
        self.target = os.path.abspath(target)
        self.recent_changes: list[float] = []
        self._last_event: dict[str, float] = {}  # path -> last handled ts (debounce)

    # ---- event dispatch ----------------------------------------------------

    def on_modified(self, event):
        if event.is_directory:
            return
        self._dispatch(event.src_path, "modified")

    def on_created(self, event):
        if event.is_directory:
            return
        self._dispatch(event.src_path, "created")

    def on_deleted(self, event):
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        rel = os.path.relpath(event.src_path, self.target)
        console.print(f"[bold red]⚠  CANARY ALERT — File deleted: {rel}[/bold red]")
        log_event("deletion", {"file": rel})
        render_risk_bar(60, "Deletion Risk")

    # ---- filtering ---------------------------------------------------------

    def _should_ignore(self, path: str) -> bool:
        abspath = os.path.abspath(path)
        # Always ignore paths inside .canary/ (checkpoints + session.json)
        canary_dir = os.path.join(self.target, ".canary")
        if abspath.startswith(canary_dir + os.sep) or abspath == canary_dir:
            return True
        # Ignore configured directories anywhere in the path
        parts = set(Path(abspath).parts)
        if parts & set(self.cfg["ignore_dirs"]):
            return True
        # Ignore configured extensions
        ext = os.path.splitext(abspath)[1].lower()
        if ext in self.cfg["ignore_exts"]:
            return True
        return False

    def _debounce(self, path: str) -> bool:
        """Return True if this event should be handled; False if it's a repeat."""
        now = time.time()
        last = self._last_event.get(path, 0.0)
        if now - last < 0.3:  # 300 ms debounce
            return False
        self._last_event[path] = now
        return True

    # ---- core handler ------------------------------------------------------

    def _dispatch(self, path: str, event_type: str):
        if self._should_ignore(path):
            return
        if not self._debounce(path):
            return

        rel = os.path.relpath(path, self.target)

        # Sensitive file guard: log + interactive confirm, but never embed.
        if is_sensitive(path, self.cfg["sensitive_patterns"]):
            console.print(
                f"\n[bold red]🚨 CANARY HARD STOP — Sensitive file {event_type}: {rel}[/bold red]"
            )
            log_event("sensitive_file_access", {"file": rel, "event": event_type})
            render_risk_bar(85, "Sensitive File Risk")
            try:
                confirm = input("Allow agent to continue? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = "n"
            if confirm != "y":
                console.print("[red]Flagged. (File is already on disk — stop your agent now.)[/red]")
            return  # never embed sensitive files

        # File-size / binary guard
        try:
            size = os.path.getsize(path)
        except OSError:
            return
        if size > self.cfg["max_file_size_bytes"]:
            log_event("skipped_large_file", {"file": rel, "size": size})
            return
        if looks_binary(path):
            log_event("skipped_binary_file", {"file": rel})
            return

        # Change-rate tracking
        now = time.time()
        window = self.cfg["change_rate_window"]
        self.recent_changes = [t for t in self.recent_changes if now - t < window]
        self.recent_changes.append(now)
        if len(self.recent_changes) > self.cfg["change_rate_limit"]:
            console.print(
                f"[yellow]⚠  CANARY ALERT — {len(self.recent_changes)} files changed in {window}s[/yellow]"
            )
            log_event("change_rate_alert", {"count": len(self.recent_changes)})
            render_risk_bar(55, "Change Rate Risk")

        # Read + embed
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError as e:
            console.print(f"[dim]canary: could not read {rel}: {e}[/dim]")
            return
        if not content.strip():
            return

        try:
            new_embedding = get_embedding(content)
        except Exception as e:
            console.print(f"[dim]canary: embedding failed for {rel}: {e}[/dim]")
            return

        baseline_embedding = self.baseline.get(path)
        if baseline_embedding is not None:
            sim = cosine_similarity(baseline_embedding, new_embedding)
            drift = round(1 - sim, 4)
            filename = os.path.basename(path)
            score = min(int(drift * 200), 100)

            console.print(f"  [dim]{rel}[/dim] drift: {drift:.4f}")
            render_risk_bar(score, "")

            threshold = (
                self.cfg["drift_entry_point"]
                if filename in self.cfg["entry_points"]
                else self.cfg["drift_alert"]
            )
            if drift > threshold:
                console.print(
                    f"[bold red]⚠  CANARY ALERT — Significant drift in {rel} "
                    f"({drift:.4f} > {threshold})[/bold red]"
                )
                log_event("drift_alert", {"file": rel, "drift": drift, "threshold": threshold})

        self.baseline[path] = new_embedding
        log_event(event_type, {"file": rel})


def _build_baseline(target: str, cfg: dict) -> dict[str, list[float]]:
    """Walk target, embed every non-ignored, non-binary, non-sensitive text file."""
    baseline: dict[str, list[float]] = {}
    target = os.path.abspath(target)
    for root, dirs, files in os.walk(target):
        # Prune ignored dirs in-place
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in cfg["ignore_dirs"]
        ]
        # Also skip .canary explicitly (starts with .)
        for fname in files:
            path = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext in cfg["ignore_exts"]:
                continue
            # Never embed sensitive files — not even for baseline
            if is_sensitive(path, cfg["sensitive_patterns"]):
                continue
            try:
                if os.path.getsize(path) > cfg["max_file_size_bytes"]:
                    continue
            except OSError:
                continue
            if looks_binary(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except OSError:
                continue
            if not content.strip():
                continue
            try:
                baseline[path] = get_embedding(content)
            except Exception as e:
                console.print(f"[dim]canary: baseline embed failed for {path}: {e}[/dim]")
    return baseline


def start_watch(target: str):
    target = os.path.abspath(target)
    cfg = load_config(target)

    console.print(f"[green]canary watching {target}...[/green]")
    console.print("[dim]Ctrl+C to stop. Run `canary rollback` to undo changes.[/dim]\n")

    baseline = _build_baseline(target, cfg)

    take_snapshot(target)
    console.print(
        f"[green]✓ Checkpoint #0 created. Watching {len(baseline)} files.[/green]\n"
    )

    handler = CanaryHandler(baseline, cfg, target)
    observer = Observer()
    observer.schedule(handler, target, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    console.print("\n[dim]canary stopped.[/dim]")
```

---

## 7. Drift (`canary/drift.py`)

```python
"""Cosine similarity for drift calculation."""
import math


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Return cosine similarity in [-1, 1]. Returns 1.0 for zero-magnitude inputs."""
    if not v1 or not v2:
        return 1.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 1.0
    return dot / (mag1 * mag2)
```

---

## 8. Sensitive File Patterns (`canary/sensitive_files.py`)

```python
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
```

---

## 9. Checkpoint and Rollback (`canary/checkpoint.py`)

```python
"""Checkpoint snapshots and rollback. Rollback is itself reversible."""
import json
import os
import shutil
import time

CANARY_DIR = ".canary"
CHECKPOINTS_DIRNAME = "checkpoints"
IGNORE_NAMES = (".canary", ".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build")


def _canary_dir(target: str) -> str:
    return os.path.join(target, CANARY_DIR)


def _checkpoints_dir(target: str) -> str:
    return os.path.join(_canary_dir(target), CHECKPOINTS_DIRNAME)


def _write_gitignore(target: str) -> None:
    """Drop a .gitignore inside .canary/ so session data doesn't leak into git."""
    cdir = _canary_dir(target)
    os.makedirs(cdir, exist_ok=True)
    gi = os.path.join(cdir, ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w") as f:
            f.write("# canary session data — not for version control\n*\n")


def take_snapshot(target: str, name: str | None = None) -> str:
    """Copy every non-ignored file from target to .canary/checkpoints/<id>/."""
    _write_gitignore(target)
    cps = _checkpoints_dir(target)
    os.makedirs(cps, exist_ok=True)
    checkpoint_id = name or f"checkpoint_{int(time.time())}"
    dest = os.path.join(cps, checkpoint_id)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(
        target,
        dest,
        ignore=shutil.ignore_patterns(*IGNORE_NAMES),
    )
    meta = {"id": checkpoint_id, "timestamp": time.time(), "target": os.path.abspath(target)}
    with open(os.path.join(dest, ".canary_meta.json"), "w") as f:
        json.dump(meta, f)
    return checkpoint_id


def list_checkpoints(target: str = ".") -> list[dict]:
    cps = _checkpoints_dir(target)
    if not os.path.exists(cps):
        return []
    out = []
    for name in sorted(os.listdir(cps)):
        meta_path = os.path.join(cps, name, ".canary_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                out.append(json.load(f))
    return out


def rollback(target: str, checkpoint_id: str | None = None) -> tuple[str, str]:
    """Revert target to the given (or most recent) checkpoint.

    Returns (restored_id, backup_id). The current state is snapshotted as
    `rollback_backup_<epoch>` before restoring, making rollback reversible.
    """
    checkpoints = list_checkpoints(target)
    if not checkpoints:
        raise RuntimeError("No checkpoints found. Run `canary watch` first.")

    if checkpoint_id is None:
        checkpoint = checkpoints[-1]
    else:
        matches = [c for c in checkpoints if c["id"] == checkpoint_id]
        if not matches:
            raise RuntimeError(f"Checkpoint '{checkpoint_id}' not found.")
        checkpoint = matches[0]

    # Back up current state first
    backup_id = f"rollback_backup_{int(time.time())}"
    take_snapshot(target, backup_id)

    # Restore
    src = os.path.join(_checkpoints_dir(target), checkpoint["id"])
    for item in os.listdir(src):
        if item == ".canary_meta.json":
            continue
        s = os.path.join(src, item)
        d = os.path.join(target, item)
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)

    return checkpoint["id"], backup_id
```

---

## 10. Session Log (`canary/session.py`)

```python
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
```

---

## 11. CLI (`canary/cli.py`)

```python
"""Click CLI entrypoint. Commands: prompt, watch, checkpoint, rollback, log, checkpoints, version."""
import datetime
import json as _json
import click
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

from . import __version__
from .prompt_firewall import scan_prompt
from .risk import render_findings, compute_risk_score
from .watcher import start_watch
from .checkpoint import take_snapshot, rollback as do_rollback, list_checkpoints
from .session import read_log, log_event

console = Console()


@click.group()
@click.version_option(__version__, prog_name="canary")
def cli():
    """canary — AI agent watchdog. Guards your prompts and your codebase."""


@cli.command("prompt")
@click.argument("text")
@click.option("--strict", is_flag=True, help="Block automatically without prompting.")
def prompt_cmd(text, strict):
    """Scan a prompt for secrets and PII before sending to an AI agent."""
    findings = scan_prompt(text)
    score = compute_risk_score(findings)
    render_findings(findings, score)

    # Log scan (never log raw matched text)
    log_event("prompt_scan", {
        "score": score,
        "finding_count": len(findings),
        "severities": [f.severity for f in findings],
    })

    if findings:
        if strict:
            console.print("[red]Blocked by canary (--strict mode).[/red]")
            raise SystemExit(1)
        try:
            confirm = input("\nSend prompt anyway? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            confirm = "n"
        if confirm != "y":
            console.print("[red]Prompt blocked.[/red]")
            raise SystemExit(1)


@cli.command("watch")
@click.argument("target", default=".", type=click.Path(exists=True))
def watch_cmd(target):
    """Watch a directory for suspicious agent activity."""
    start_watch(target)


@cli.command("checkpoint")
@click.argument("target", default=".", type=click.Path(exists=True))
def checkpoint_cmd(target):
    """Save a clean checkpoint of the current state."""
    cid = take_snapshot(target)
    console.print(f"[green]✓ Checkpoint saved: {cid}[/green]")


@cli.command("rollback")
@click.argument("target", default=".", type=click.Path(exists=True))
@click.argument("checkpoint_id", required=False)
def rollback_cmd(target, checkpoint_id):
    """Roll back all changes to the last (or specified) checkpoint."""
    try:
        restored, backup = do_rollback(target, checkpoint_id)
        console.print(f"[green]✓ Rolled back to: {restored}[/green]")
        console.print(f"[dim]Current state backed up to: {backup}[/dim]")
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@cli.command("log")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON.")
@click.option("--tail", type=int, default=None, help="Show only the last N events.")
@click.argument("target", default=".", type=click.Path(exists=True))
def log_cmd(output_json, tail, target):
    """Show the full session event log."""
    events = read_log(target)
    if tail:
        events = events[-tail:]
    if output_json:
        print(_json.dumps(events, indent=2))
        return
    if not events:
        console.print("[dim]No events logged yet.[/dim]")
        return
    for e in events:
        ts = datetime.datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S")
        rest = {k: v for k, v in e.items() if k not in ("timestamp", "type")}
        console.print(f"[dim]{ts}[/dim] [{e['type']}] {_json.dumps(rest)}")


@cli.command("checkpoints")
@click.argument("target", default=".", type=click.Path(exists=True))
def checkpoints_cmd(target):
    """List all saved checkpoints."""
    cps = list_checkpoints(target)
    if not cps:
        console.print("[dim]No checkpoints found.[/dim]")
        return
    for c in cps:
        ts = datetime.datetime.fromtimestamp(c["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"[green]{c['id']}[/green] — {ts}")


if __name__ == "__main__":
    cli()
```

---

## 12. Mock Mode (`canary/mock.py`)

```python
"""Deterministic mock embeddings for dev/demo/CI without IBM credentials."""
import os
import random

IBM_MOCK = os.environ.get("IBM_MOCK", "false").strip().lower() == "true"

EMBEDDING_DIM = 768


def mock_embedding(seed: str = "") -> list[float]:
    """Return a deterministic 768-dim vector seeded by `seed`.

    Same seed → same vector. Different seeds → (almost always) different vectors.
    The values are in [-1, 1].
    """
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIM)]
```

---

## 13. Binary Detection (`canary/binary.py`)

```python
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
```

---

## 14. Configuration Loader (`canary/config.py`)

```python
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
```

---

## 15. Package Init (`canary/__init__.py`)

```python
"""canary — AI agent watchdog."""

__version__ = "0.1.0"
```

---

## 16. Tests

### §16.1 `tests/__init__.py`

```python
```

### §16.2 `tests/test_firewall.py`

```python
from canary.prompt_firewall import scan_prompt, luhn_valid, shannon_entropy


def test_no_findings_on_safe_prompt():
    findings = scan_prompt("Fix the bug in the login function, please.")
    assert findings == []


def test_openai_key_flagged():
    findings = scan_prompt("my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ fix things")
    kinds = [f.description for f in findings]
    assert any("OpenAI" in k or "Anthropic" in k for k in kinds)
    assert all(f.severity == "CRITICAL" for f in findings if "OpenAI" in f.description)


def test_github_token_flagged():
    findings = scan_prompt("GH token ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    assert any("GitHub" in f.description for f in findings)


def test_aws_key_flagged():
    findings = scan_prompt("aws key AKIAIOSFODNN7EXAMPLE in the prompt")
    assert any("AWS" in f.description for f in findings)


def test_email_flagged_medium():
    findings = scan_prompt("contact me at john.doe@example.com")
    assert any(f.description == "Email address" and f.severity == "MEDIUM" for f in findings)


def test_ssn_flagged_critical():
    findings = scan_prompt("my ssn is 123-45-6789")
    assert any("SSN" in f.description and f.severity == "CRITICAL" for f in findings)


def test_luhn_valid_credit_card():
    # Visa test number
    assert luhn_valid("4111111111111111")
    # Invalid
    assert not luhn_valid("4111111111111112")


def test_credit_card_requires_luhn():
    good = "my card 4111111111111111 is fine"
    bad  = "random number 1234567890123456 is not a card"
    good_findings = [f for f in scan_prompt(good) if "Credit card" in f.description]
    bad_findings  = [f for f in scan_prompt(bad)  if "Credit card" in f.description]
    assert good_findings
    assert not bad_findings


def test_entropy_ignores_git_sha():
    # Git SHA should NOT be flagged as entropy even though it's high-entropy
    findings = scan_prompt("commit abc1234567890abcdef1234567890abcdef12345678")
    entropy_findings = [f for f in findings if f.kind == "entropy"]
    assert not entropy_findings


def test_entropy_flags_unknown_high_entropy():
    token = "Xk9!vP2mQ@7zLw4bN8cR3sT6aE1u"  # > 20 chars, high entropy, not a known pattern
    findings = scan_prompt(f"here is {token}")
    assert any(f.kind == "entropy" for f in findings)


def test_shannon_entropy_basic():
    assert shannon_entropy("") == 0.0
    assert shannon_entropy("aaaa") == 0.0
    assert shannon_entropy("ab") == 1.0
```

### §16.3 `tests/test_drift.py`

```python
from canary.drift import cosine_similarity


def test_identical_vectors():
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == 1.0


def test_orthogonal_vectors():
    assert cosine_similarity([1, 0], [0, 1]) == 0.0


def test_zero_vector_handled():
    assert cosine_similarity([0, 0, 0], [1, 2, 3]) == 1.0


def test_empty_vector_handled():
    assert cosine_similarity([], [1, 2, 3]) == 1.0
```

### §16.4 `tests/test_sensitive_files.py`

```python
from canary.sensitive_files import is_sensitive


def test_env_file_sensitive():
    assert is_sensitive("/tmp/.env")
    assert is_sensitive("/tmp/.env.production")


def test_private_keys_sensitive():
    assert is_sensitive("/home/u/.ssh/id_rsa")
    assert is_sensitive("/home/u/.ssh/id_ed25519")
    assert is_sensitive("/tmp/server.key")
    assert is_sensitive("/tmp/cert.pem")


def test_normal_files_not_sensitive():
    assert not is_sensitive("/tmp/main.py")
    assert not is_sensitive("/tmp/README.md")
```

---

## 17. Environment Variables (`.env.example`)

```
# Required for live mode. Get from IBM Cloud → Manage → Access → API Keys.
IBM_API_KEY=

# Required for live mode. Get from watsonx.ai → Projects → Manage.
IBM_PROJECT_ID=

# Region endpoint. One of: us-south | eu-de | jp-tok | eu-gb | au-syd
IBM_REGION=us-south

# Set to `true` to use deterministic mock embeddings (no API calls made).
# Useful for dev, CI, and offline demos.
IBM_MOCK=false
```

---

## 18. Config Example (`.canary.toml.example`)

```toml
# Copy this to `.canary.toml` in the directory you intend to `canary watch`.
# All keys are optional; missing keys fall back to built-in defaults.

[thresholds]
drift_alert = 0.15            # any file above this cosine-distance triggers an alert
drift_entry_point = 0.08      # entry-point files use a tighter threshold
change_rate_window = 60       # seconds
change_rate_limit = 10        # more than this many changes in the window triggers an alert
max_file_size_bytes = 524288  # 512 KB; larger files are skipped

[entry_points]
files = ["main.py", "app.py", "index.ts", "index.js", "server.py", "__init__.py"]

[ignore]
dirs = [".git", ".canary", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"]
extensions = [".pyc", ".so", ".png", ".jpg", ".pdf", ".zip"]

[sensitive]
patterns = [
  ".env", ".env.*",
  "*.key", "*.pem", "*.p12", "*.pfx",
  "id_rsa", "id_ed25519",
  "secrets.*", "credentials.*",
  "*password*", "*token*", "*.secret",
]
```

---

## 19. Requirements (`requirements.txt`)

```
click>=8.1
rich>=13.0
requests>=2.31
watchdog>=3.0
python-dotenv>=1.0
tomli>=2.0 ; python_version < "3.11"
pytest>=7.0
```

---

## 20. Setup (`setup.py`)

```python
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    reqs = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="canary-watch",
    version="0.1.0",
    description="AI agent watchdog: prompt firewall + filesystem drift detection via IBM Granite.",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.10",
    install_requires=reqs,
    entry_points={"console_scripts": ["canary=canary.cli:cli"]},
)
```

---

## 21. Pyproject (`pyproject.toml`)

```toml
[build-system]
requires = ["setuptools>=61", "wheel"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## 22. Top-level Gitignore (`.gitignore`)

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.mypy_cache/
build/
dist/

# Env
.env
.env.local

# Canary session state
.canary/

# OS
.DS_Store
Thumbs.db
```
