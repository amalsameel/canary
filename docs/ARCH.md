# canary — Architecture Document

**Version:** 0.2.0
**Last updated:** 2026-04-18

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
                        │   - PII detection           │
                        │   - entropy analysis        │
                        │   - risk score bar          │
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
                        │   - filesystem monitor      │
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
│   ├── __init__.py
│   ├── cli.py                  # Click CLI entrypoint
│   ├── prompt_firewall.py      # Prompt scanning (secrets, PII, entropy)
│   ├── watcher.py              # Filesystem watchdog (watchdog library)
│   ├── drift.py                # Cosine similarity + drift classification
│   ├── checkpoint.py           # Checkpoint creation and rollback
│   ├── risk.py                 # Risk score computation + progress bar renderer
│   ├── sensitive_files.py      # Sensitive file pattern matching
│   ├── session.py              # Session log read/write
│   ├── ibm/
│   │   ├── __init__.py
│   │   ├── iam.py              # IBM IAM token refresh
│   │   └── embeddings.py       # Granite embedding call + cache
│   └── mock.py                 # Mock IBM responses
├── tests/
│   ├── fixtures/
│   │   ├── safe_prompt.txt
│   │   ├── leaky_prompt.txt    # contains fake API key
│   │   └── sample_project/     # small project for watchdog tests
│   └── test_firewall.py
├── .env.example
├── .canary.toml.example        # default thresholds config
├── requirements.txt
├── setup.py
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
import time, requests, os

_token_cache = {"token": None, "expires_at": 0}

def get_iam_token() -> str:
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    resp = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": os.environ["IBM_API_KEY"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data["expires_in"]
    return _token_cache["token"]
```

### §3.2 Granite Embedding (`canary/ibm/embeddings.py`)

```python
import hashlib, requests, os
from .iam import get_iam_token
from ..mock import IBM_MOCK, mock_embedding

_cache: dict[str, list[float]] = {}

def get_embedding(text: str) -> list[float]:
    key = hashlib.sha256(text.encode()).hexdigest()
    if key in _cache:
        return _cache[key]
    if IBM_MOCK:
        return mock_embedding(key)

    token = get_iam_token()
    resp = requests.post(
        "https://us-south.ml.cloud.ibm.com/ml/v1/text/embeddings?version=2024-05-31",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "model_id": "ibm/granite-embedding-278m-multilingual",
            "project_id": os.environ["IBM_PROJECT_ID"],
            "inputs": [text[:8000]],
        },
    )
    resp.raise_for_status()
    vector = resp.json()["results"][0]["embedding"]
    _cache[key] = vector
    return vector
```

---

## 4. Prompt Firewall (`canary/prompt_firewall.py`)

```python
import re, math, string
from dataclasses import dataclass

@dataclass
class PromptFinding:
    kind: str
    severity: str        # CRITICAL | HIGH | MEDIUM
    description: str
    matched: str         # the actual matched text (redacted in display)
    score: int           # risk points

# Known secret prefixes
SECRET_PATTERNS = [
    (r'sk-[A-Za-z0-9]{20,}', 'OpenAI / Anthropic API key', 'CRITICAL', 40),
    (r'ghp_[A-Za-z0-9]{36}', 'GitHub personal access token', 'CRITICAL', 40),
    (r'xox[baprs]-[A-Za-z0-9\-]{10,}', 'Slack token', 'CRITICAL', 40),
    (r'AKIA[0-9A-Z]{16}', 'AWS access key', 'CRITICAL', 40),
    (r'AIza[0-9A-Za-z\-_]{35}', 'Google API key', 'CRITICAL', 40),
    (r'(?i)(password|passwd|pwd)\s*[=:]\s*\S{6,}', 'Possible password', 'HIGH', 30),
    (r'(?i)(secret|token|api_key|apikey)\s*[=:]\s*\S{8,}', 'Possible secret', 'HIGH', 30),
]

# PII patterns
PII_PATTERNS = [
    (r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', 'Email address', 'MEDIUM', 20),
    (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN', 'CRITICAL', 40),
    (r'\b(?:\d[ -]?){13,16}\b', 'Possible credit card number', 'HIGH', 30),
    (r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', 'Phone number', 'MEDIUM', 10),
]

# Sensitive paths
PATH_PATTERNS = [
    (r'/etc/passwd', 'System password file path', 'HIGH', 25),
    (r'~/\.ssh/', 'SSH directory path', 'HIGH', 25),
    (r'\.env\b', '.env file reference', 'HIGH', 25),
    (r'id_rsa|id_ed25519', 'Private key file reference', 'CRITICAL', 40),
]

def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    return -sum((c / len(s)) * math.log2(c / len(s)) for c in counts.values())

def scan_prompt(text: str) -> list[PromptFinding]:
    findings = []

    for pattern, description, severity, score in SECRET_PATTERNS + PII_PATTERNS + PATH_PATTERNS:
        for match in re.finditer(pattern, text):
            findings.append(PromptFinding(
                kind="secret" if score >= 30 else "pii",
                severity=severity,
                description=description,
                matched=match.group(),
                score=score,
            ))

    # Entropy-based high-entropy string detection
    for token in text.split():
        clean = token.strip(string.punctuation)
        if len(clean) > 20 and shannon_entropy(clean) > 4.5:
            # Avoid double-flagging already caught patterns
            if not any(f.matched == clean for f in findings):
                findings.append(PromptFinding(
                    kind="entropy",
                    severity="HIGH",
                    description="High-entropy string (possible secret)",
                    matched=clean,
                    score=25,
                ))

    return findings
```

---

## 5. Risk Score and Progress Bar (`canary/risk.py`)

```python
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from rich.style import Style

console = Console()

def compute_risk_score(findings: list) -> int:
    return min(sum(f.score for f in findings), 100)

def bar_color(score: int) -> str:
    if score <= 30:
        return "green"
    elif score <= 60:
        return "yellow"
    else:
        return "red"

def render_risk_bar(score: int, label: str = "Risk Score"):
    color = bar_color(score)
    filled = int(score / 5)       # 20 blocks total
    empty = 20 - filled
    bar = "█" * filled + "░" * empty
    console.print(f"{label}: [{color}][{bar}] {score}%[/{color}]")

def render_findings(findings: list, score: int):
    if not findings:
        console.print("[green]✓ No sensitive data detected[/green]")
        render_risk_bar(score)
        return

    console.print()
    for f in findings:
        color = {"CRITICAL": "bold red", "HIGH": "red", "MEDIUM": "yellow"}.get(f.severity, "white")
        redacted = f.matched[:4] + "..." + f.matched[-2:] if len(f.matched) > 8 else "***"
        console.print(f"  [{color}][{f.severity}][/{color}] {f.description} — [dim]{redacted}[/dim]")
    console.print()
    render_risk_bar(score)
```

---

## 6. Filesystem Watchdog (`canary/watcher.py`)

```python
import time, os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .ibm.embeddings import get_embedding
from .drift import cosine_similarity
from .sensitive_files import is_sensitive
from .checkpoint import take_snapshot
from .session import log_event
from .risk import render_risk_bar, compute_risk_score
from rich.console import Console

console = Console()

DRIFT_ALERT = 0.15
DRIFT_ENTRY_POINT = 0.08
ENTRY_POINTS = {"main.py", "app.py", "index.ts", "index.js", "server.py"}
CHANGE_RATE_WINDOW = 60   # seconds
CHANGE_RATE_LIMIT = 10

class CanaryHandler(FileSystemEventHandler):
    def __init__(self, baseline_embeddings: dict[str, list[float]]):
        self.baseline = baseline_embeddings
        self.recent_changes: list[float] = []

    def on_modified(self, event):
        if event.is_directory:
            return
        self._handle(event.src_path, "modified")

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle(event.src_path, "created")

    def on_deleted(self, event):
        console.print(f"[bold red]⚠  CANARY ALERT — File deleted: {event.src_path}[/bold red]")
        log_event("deletion", {"file": event.src_path})
        render_risk_bar(60, "Deletion Risk")

    def _handle(self, path: str, event_type: str):
        # Sensitive file guard
        if is_sensitive(path):
            console.print(f"\n[bold red]🚨 CANARY HARD STOP — Sensitive file accessed: {path}[/bold red]")
            log_event("sensitive_file_access", {"file": path})
            render_risk_bar(85, "Sensitive File Risk")
            confirm = input("Allow agent to access this file? [y/N] ").strip().lower()
            if confirm != "y":
                console.print("[red]Access blocked by canary.[/red]")
                return

        # Change rate check
        now = time.time()
        self.recent_changes = [t for t in self.recent_changes if now - t < CHANGE_RATE_WINDOW]
        self.recent_changes.append(now)
        if len(self.recent_changes) > CHANGE_RATE_LIMIT:
            console.print(f"[yellow]⚠  CANARY ALERT — {len(self.recent_changes)} files changed in 60s[/yellow]")
            render_risk_bar(55, "Change Rate Risk")

        # Drift detection
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if not content.strip():
                return

            new_embedding = get_embedding(content)
            baseline_embedding = self.baseline.get(path)

            if baseline_embedding:
                sim = cosine_similarity(baseline_embedding, new_embedding)
                drift = round(1 - sim, 4)
                filename = os.path.basename(path)
                score = min(int(drift * 200), 100)

                console.print(f"  [dim]{filename}[/dim] drift: {drift:.4f} ", end="")
                render_risk_bar(score, "")

                threshold = DRIFT_ENTRY_POINT if filename in ENTRY_POINTS else DRIFT_ALERT
                if drift > threshold:
                    console.print(f"[bold red]⚠  CANARY ALERT — Significant drift in {filename} ({drift:.4f})[/bold red]")
                    log_event("drift_alert", {"file": path, "drift": drift})

            # Update baseline
            self.baseline[path] = new_embedding
            log_event(event_type, {"file": path})

        except Exception as e:
            console.print(f"[dim]canary: could not process {path}: {e}[/dim]")


def start_watch(target: str):
    console.print(f"[green]canary watching {target}...[/green]")
    console.print("[dim]Ctrl+C to stop. Run `canary rollback` to undo changes.[/dim]\n")

    # Build baseline embeddings
    baseline = {}
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"node_modules", "__pycache__", "venv"}]
        for fname in files:
            path = os.path.join(root, fname)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if content.strip():
                    baseline[path] = get_embedding(content)
            except Exception:
                pass

    take_snapshot(target)
    console.print(f"[green]✓ Checkpoint #0 created. Watching {len(baseline)} files.[/green]\n")

    handler = CanaryHandler(baseline)
    observer = Observer()
    observer.schedule(handler, target, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

---

## 7. Drift (`canary/drift.py`)

```python
import math

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 1.0
    return dot / (mag1 * mag2)
```

---

## 8. Sensitive File Patterns (`canary/sensitive_files.py`)

```python
import fnmatch, os

SENSITIVE_PATTERNS = [
    ".env", ".env.*",
    "*.key", "*.pem", "*.p12", "*.pfx",
    "id_rsa", "id_ed25519", "id_dsa",
    "secrets.*", "credentials.*",
    "*password*", "*passwd*",
    "*token*", "*.secret",
    "*.keystore", "*.jks",
]

def is_sensitive(path: str) -> bool:
    filename = os.path.basename(path)
    return any(fnmatch.fnmatch(filename, pattern) for pattern in SENSITIVE_PATTERNS)
```

---

## 9. Checkpoint and Rollback (`canary/checkpoint.py`)

```python
import os, shutil, json, time
from pathlib import Path

CANARY_DIR = ".canary"
CHECKPOINTS_DIR = os.path.join(CANARY_DIR, "checkpoints")

def _checkpoint_path(checkpoint_id: str) -> str:
    return os.path.join(CHECKPOINTS_DIR, checkpoint_id)

def take_snapshot(target: str, name: str = None) -> str:
    os.makedirs(CHECKPOINTS_DIR, exist_ok=True)
    checkpoint_id = name or f"checkpoint_{int(time.time())}"
    dest = _checkpoint_path(checkpoint_id)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(target, dest, ignore=shutil.ignore_patterns(".canary", ".git", "node_modules", "__pycache__"))
    # Record metadata
    meta = {"id": checkpoint_id, "timestamp": time.time(), "target": target}
    with open(os.path.join(dest, ".canary_meta.json"), "w") as f:
        json.dump(meta, f)
    return checkpoint_id

def list_checkpoints() -> list[dict]:
    if not os.path.exists(CHECKPOINTS_DIR):
        return []
    checkpoints = []
    for name in sorted(os.listdir(CHECKPOINTS_DIR)):
        meta_path = os.path.join(CHECKPOINTS_DIR, name, ".canary_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                checkpoints.append(json.load(f))
    return checkpoints

def rollback(target: str, checkpoint_id: str = None):
    checkpoints = list_checkpoints()
    if not checkpoints:
        raise RuntimeError("No checkpoints found. Run `canary watch` first.")

    if checkpoint_id is None:
        checkpoint = checkpoints[-1]
    else:
        matches = [c for c in checkpoints if c["id"] == checkpoint_id]
        if not matches:
            raise RuntimeError(f"Checkpoint '{checkpoint_id}' not found.")
        checkpoint = matches[0]

    # Backup current state before rollback
    backup_id = f"rollback_backup_{int(time.time())}"
    take_snapshot(target, backup_id)

    # Restore
    src = _checkpoint_path(checkpoint["id"])
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
import json, os, time

CANARY_DIR = ".canary"
SESSION_FILE = os.path.join(CANARY_DIR, "session.json")

def log_event(event_type: str, data: dict):
    os.makedirs(CANARY_DIR, exist_ok=True)
    events = []
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE) as f:
            events = json.load(f)
    events.append({"timestamp": time.time(), "type": event_type, **data})
    with open(SESSION_FILE, "w") as f:
        json.dump(events, f, indent=2)

def read_log() -> list[dict]:
    if not os.path.exists(SESSION_FILE):
        return []
    with open(SESSION_FILE) as f:
        return json.load(f)
```

---

## 11. CLI (`canary/cli.py`)

```python
import click
from dotenv import load_dotenv
load_dotenv()

from .prompt_firewall import scan_prompt
from .risk import render_findings, render_risk_bar, compute_risk_score
from .watcher import start_watch
from .checkpoint import take_snapshot, rollback, list_checkpoints
from .session import read_log
from rich.console import Console
import json as _json

console = Console()

@click.group()
def cli():
    """canary — AI agent watchdog. Guards your prompts and your codebase."""
    pass

@cli.command()
@click.argument("text")
@click.option("--strict", is_flag=True, help="Block automatically without prompting")
def prompt(text, strict):
    """Scan a prompt for secrets and PII before sending to an AI agent."""
    findings = scan_prompt(text)
    score = compute_risk_score(findings)
    render_findings(findings, score)

    if findings:
        if strict:
            console.print("[red]Blocked by canary (--strict mode).[/red]")
            raise SystemExit(1)
        confirm = input("\nSend prompt anyway? [y/N] ").strip().lower()
        if confirm != "y":
            console.print("[red]Prompt blocked.[/red]")
            raise SystemExit(1)

@cli.command()
@click.argument("target", default=".", type=click.Path(exists=True))
def watch(target):
    """Watch a directory for suspicious agent activity."""
    start_watch(target)

@cli.command()
@click.argument("target", default=".", type=click.Path(exists=True))
def checkpoint(target):
    """Save a clean checkpoint of the current state."""
    cid = take_snapshot(target)
    console.print(f"[green]✓ Checkpoint saved: {cid}[/green]")

@cli.command()
@click.argument("target", default=".", type=click.Path(exists=True))
@click.argument("checkpoint_id", required=False)
def rollback_cmd(target, checkpoint_id):
    """Roll back all changes to the last (or specified) checkpoint."""
    try:
        restored, backup = rollback(target, checkpoint_id)
        console.print(f"[green]✓ Rolled back to: {restored}[/green]")
        console.print(f"[dim]Current state backed up to: {backup}[/dim]")
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

@cli.command()
@click.option("--json", "output_json", is_flag=True)
def log(output_json):
    """Show the full session event log."""
    events = read_log()
    if output_json:
        print(_json.dumps(events, indent=2))
        return
    if not events:
        console.print("[dim]No events logged yet.[/dim]")
        return
    for e in events:
        import datetime
        ts = datetime.datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S")
        console.print(f"[dim]{ts}[/dim] [{e['type']}] {_json.dumps({k: v for k, v in e.items() if k not in ('timestamp', 'type')})}")

@cli.command()
def checkpoints():
    """List all saved checkpoints."""
    cps = list_checkpoints()
    if not cps:
        console.print("[dim]No checkpoints found.[/dim]")
        return
    for c in cps:
        import datetime
        ts = datetime.datetime.fromtimestamp(c["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"[green]{c['id']}[/green] — {ts}")

if __name__ == "__main__":
    cli()
```

---

## 12. Mock Mode (`canary/mock.py`)

```python
import os, hashlib, random

IBM_MOCK = os.environ.get("IBM_MOCK", "false").lower() == "true"

def mock_embedding(seed: str = "") -> list[float]:
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(768)]
```

---

## 13. Environment Variables (`.env.example`)

```
IBM_API_KEY=
IBM_PROJECT_ID=
IBM_MOCK=false
```

---

## 14. Requirements (`requirements.txt`)

```
click>=8.1
rich>=13.0
requests>=2.31
watchdog>=3.0
python-dotenv>=1.0
```

---

## 15. Setup (`setup.py`)

```python
from setuptools import setup, find_packages
setup(
    name="canary-watch",
    version="0.1.0",
    packages=find_packages(),
    install_requires=open("requirements.txt").read().splitlines(),
    entry_points={"console_scripts": ["canary=canary.cli:cli"]},
)
```
