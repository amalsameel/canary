# canary

**You let the AI agent loose. Canary makes sure it doesn't burn the house down.**

> Built for Hook 'Em Hacks 2026 · Security in an AI-First World track (IBM-sponsored)

---

## What it does

AI coding agents (Claude Code, Cursor, Devin) now autonomously read, write, and modify your codebase. Two things can go wrong that no existing tool catches:

1. **You leak secrets in your prompt** — paste an API key into a chat window and it's gone
2. **The agent goes off the rails** — reads your `.env`, drifts your entry point, rewrites 30 files you didn't ask it to touch

Canary sits between you, the agent, and your codebase — watching both directions.

---

## Demo

```
$ canary prompt "here's my openai key sk-abc123xyz, fix the auth bug"

  [CRITICAL] OpenAI / Anthropic API key — sk-a...yz
  [MEDIUM]   No other findings

  Risk Score: [████████████████░░░░] 78%

Send prompt anyway? [y/N]
```

```
$ canary watch ./src

  canary watching ./src...
  ✓ Checkpoint #0 created. Watching 34 files.

  🚨 CANARY HARD STOP — Sensitive file accessed: .env
  Allow agent to access this file? [y/N]

  auth.py drift: 0.1823
  Risk Score: [█████████████░░░░░░░] 62%
  ⚠  CANARY ALERT — Significant drift in auth.py (0.1823)
```

```
$ canary rollback

  ✓ Rolled back to: checkpoint_1713400000
  Current state backed up to: rollback_backup_1713400512
```

---

## Install

```bash
git clone https://github.com/your-org/canary
cd canary
pip install -r requirements.txt
cp .env.example .env
# Fill in IBM_API_KEY and IBM_PROJECT_ID

pip install -e .
canary --help
```

Set `IBM_MOCK=true` in `.env` to run without IBM credentials (returns mock embeddings for development).

---

## Usage

```bash
# Scan a prompt before sending to an AI agent
canary prompt "your prompt text here"
canary prompt "your prompt text" --strict   # block automatically, no confirmation

# Watch a directory while an agent is running
canary watch ./src

# Save a manual checkpoint
canary checkpoint ./src

# List all checkpoints
canary checkpoints

# Roll back to last checkpoint
canary rollback ./src

# Roll back to a specific checkpoint
canary rollback ./src checkpoint_1713400000

# View session log
canary log
canary log --json
```

---

## How it works

### Prompt Firewall (Human → Agent)
Before your prompt reaches the AI agent, canary scans it for:
- Known secret formats: OpenAI keys (`sk-`), GitHub tokens (`ghp_`), AWS keys (`AKIA`), Slack tokens (`xox`), Google API keys (`AIza`)
- High-entropy strings (Shannon entropy > 4.5 over 20+ characters) — catches novel secret formats
- PII: emails, SSNs, credit card numbers, phone numbers
- Sensitive file path references (`.env`, `~/.ssh/`, `id_rsa`)

Findings are shown with a colored risk score progress bar. You confirm or block before the prompt goes anywhere.

### File Watchdog (Agent → Codebase)
While the agent runs, canary monitors every file change using OS-level filesystem events. For each change:
- IBM Granite embeds the new content and computes semantic drift against the baseline
- Sensitive file access (`.env`, `*.key`, `*.pem`, etc.) triggers a hard stop
- Drift > 0.15 on any file triggers an alert
- Drift > 0.08 on your entry point (`main.py`, `app.py`, etc.) triggers an alert
- More than 10 files changed in 60 seconds triggers an alert
- Any file deletion triggers an alert

### Checkpoints and Rollback
On `canary watch` start, a full snapshot of your directory is taken. You can create additional checkpoints manually. `canary rollback` reverts all files to the last clean state — and backs up the current state first, so the rollback itself is reversible.

---

## Tech stack

| Layer | Tool |
|---|---|
| CLI | Python + Click |
| Terminal output | Rich (colored progress bars, live updates) |
| Filesystem monitoring | watchdog (OS-level inotify / FSEvents) |
| Semantic drift detection | IBM Granite (`ibm/granite-embedding-278m-multilingual`) via watsonx.ai |
| Secret detection | Regex + Shannon entropy |
| PII detection | Regex |

---

## Environment variables

| Variable | Where to get it |
|---|---|
| `IBM_API_KEY` | IBM Cloud → Manage → Access → API Keys |
| `IBM_PROJECT_ID` | watsonx.ai → Projects → your project → Manage |
| `IBM_MOCK` | Set to `true` to skip IBM API calls during development |

---

## Why IBM Granite?

Standard file watchers tell you *what* changed — byte diffs, line counts. IBM Granite tells you *whether the meaning changed*. A one-word edit that flips logic (`if not auth` → `if auth`) looks like a minor change in a diff but registers as high semantic drift in embedding space. That's the detection capability that makes canary's watchdog meaningful rather than noisy.

---

## Project structure

```
canary/
├── canary/
│   ├── cli.py                  # Click CLI entrypoint
│   ├── prompt_firewall.py      # Secret + PII + entropy scanning
│   ├── watcher.py              # Filesystem watchdog
│   ├── drift.py                # Cosine similarity
│   ├── checkpoint.py           # Snapshot + rollback
│   ├── risk.py                 # Risk score + progress bar
│   ├── sensitive_files.py      # Sensitive file pattern matching
│   ├── session.py              # Session event log
│   ├── mock.py                 # Mock IBM responses
│   └── ibm/                    # IBM IAM + Granite embeddings
├── tests/fixtures/             # Safe and leaky prompt fixtures
└── docs/                       # PRD, ARCH, CHANGELOG, MASTERPROMPT
```

---

## License

MIT
