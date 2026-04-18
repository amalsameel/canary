# canary — Product Requirements Document

**Version:** 0.2.0
**Status:** Draft
**Track:** Hook 'Em Hacks 2026 — Security in an AI-First World (IBM-sponsored)
**Last updated:** 2026-04-18

---

## 1. Problem Statement

AI coding agents (Claude Code, Devin, Cursor, Copilot) now autonomously read, write, and execute code on behalf of developers. This introduces two new attack surfaces that no existing tool addresses:

**Surface 1 — Prompt leakage (Human → Agent)**
Developers routinely paste API keys, passwords, environment variables, and PII directly into prompts without realizing the data is being sent to an external model. Once in the model's context, that data may be logged, cached, or used in ways the developer did not intend.

**Surface 2 — Agent misbehavior (Agent → Codebase)**
AI agents operate autonomously over extended sessions. They may read sensitive files (`.env`, `*.key`, auth configs) and incorporate their contents into context, modify far more files than the task requires, introduce semantic meaning changes that a line diff won't catch, or spiral into destructive behavior with no human checkpoint.

Current tooling does not solve this:

| Existing tool | What it does | What it misses |
|---|---|---|
| `.gitignore` | Keeps files out of version control | Does not prevent an agent from reading them |
| Secret scanners (truffleHog, gitleaks) | Scans committed code for secrets | Does not intercept secrets before they reach the model |
| Git history | Tracks file changes | Syntactic only; no semantic drift; no real-time alerting |
| AI agent sandboxes | Restrict filesystem access | Coarse-grained; no semantic awareness; no prompt inspection |

`canary` fills this gap by sitting as a two-way guard between the human, the agent, and the codebase.

---

## 2. Product Vision

> **"You let the AI agent loose. Canary makes sure it doesn't burn the house down."**

`canary` is a CLI watchdog for AI coding agent sessions. It inspects prompts before they reach the agent, monitors every file change the agent makes in real time, alerts the human when thresholds are crossed, and rolls back changes if something goes wrong.

---

## 3. Target Users

- Developers using AI coding agents (Claude Code, Cursor, Devin) on codebases with secrets or compliance obligations
- Security engineers reviewing AI-assisted PRs
- Engineering leads at companies with SOX, HIPAA, or SOC 2 obligations
- Any developer who has ever accidentally pasted a secret into a chat window

---

## 4. Use Cases

### UC-1: Prompt firewall
Developer types a prompt that accidentally includes an API key. Before the prompt reaches the agent, canary intercepts it, highlights the sensitive data, and asks for confirmation.

### UC-2: Agent file watch
Developer runs `canary watch ./src` alongside Claude Code. The agent starts modifying files. Canary tracks every change semantically using IBM Granite embeddings and alerts when drift on any file exceeds the threshold.

### UC-3: Sensitive file access alert
The agent attempts to read `.env` or `secrets.yaml`. Canary hard-stops and requires human confirmation before allowing the read.

### UC-4: Rollback
The agent has modified 23 files in a way that looks wrong. Developer runs `canary rollback` and all changes since the last checkpoint are reverted.

### UC-5: Session replay
After a session, developer runs `canary log` to see a full timeline of what the agent did, what it read, what it changed, and what drift scores were recorded.

---

## 5. Functional Requirements

### FR-1: Prompt firewall
- Intercept the user's prompt before it is sent to the agent
- Scan for:
  - API keys and tokens (regex patterns for common formats: `sk-`, `ghp_`, `xox`, `AKIA`, etc.)
  - Passwords and secrets (entropy-based detection for high-entropy strings > 20 chars)
  - PII: email addresses, phone numbers, SSNs, credit card numbers
  - File paths that expose sensitive system structure (`/etc/passwd`, `~/.ssh/`, etc.)
  - Environment variable values embedded in context
- On detection: print a warning with the specific finding highlighted, show risk score progress bar, and prompt for confirmation before proceeding
- `--strict` flag: block automatically without prompting

### FR-2: File system watchdog
- Watch a target directory recursively for any file changes made during an agent session
- On every change: compute IBM Granite embedding of the new content, compare against the sealed baseline, record the drift score
- Alert thresholds:
  - Files changed in 60 seconds > 10 → alert
  - Semantic drift on any single file > 0.15 → alert
  - Any deletion → alert
  - Any write to a critical file pattern (`*.env`, `*.key`, `*.pem`, `id_rsa`, `secrets.*`, `credentials.*`) → hard stop
  - Meaning of entry point file (`main.py`, `index.ts`, `app.py`) changes > 0.08 → alert

### FR-3: Sensitive file access detection
- Maintain a list of sensitive file patterns:
  ```
  .env, .env.*, *.key, *.pem, *.p12, id_rsa, id_ed25519,
  secrets.*, credentials.*, *password*, *token*, *.secret
  ```
- If the agent reads any matching file, canary intercepts and requires human confirmation
- Log all sensitive file access attempts regardless of outcome

### FR-4: Checkpoints and rollback
- On `canary watch` start, automatically create checkpoint `#0` (snapshot of all tracked files)
- `canary checkpoint` creates a named checkpoint at any point
- `canary rollback` reverts all files to the most recent checkpoint
- `canary rollback <id>` reverts to a specific checkpoint
- Rollback creates a `.canary/rollback_backup_<timestamp>/` before reverting, so the rollback itself is reversible

### FR-5: Risk score progress bar
- Compute a risk score 0–100 for each event based on findings
- Scoring:
  - Hardcoded secret in prompt: +40
  - PII in prompt: +20
  - Sensitive file accessed: +25
  - File drift > 0.15: +20 per file
  - > 10 files changed in 60s: +15
  - Critical file written: +40
- Display as a colored terminal progress bar using `rich`:
  - 0–30: green  `[████████░░░░░░░░░░░░] 38%`
  - 31–60: yellow `[████████████░░░░░░░░] 55%`
  - 61–100: red   `[████████████████████] 89%`
- Numeric percentage shown alongside the bar
- Bar updates in real time during `canary watch`
- No verdict labels (CLEAN / RISKY / etc.) — the bar speaks for itself

### FR-6: Session log
- `canary log` prints a full chronological timeline of the session:
  - Prompt scans (findings, risk score bar)
  - File changes (file, drift score, timestamp)
  - Alerts triggered
  - Checkpoints created
  - Rollbacks performed
- `canary log --json` outputs machine-readable JSON

### FR-7: IBM Granite semantic fingerprinting
- On session start, embed all tracked files using IBM Granite (`ibm/granite-embedding-278m-multilingual`)
- Cache embeddings by `sha256(content)` to avoid redundant API calls
- On every file change, re-embed and compute cosine similarity against the baseline
- Store all embeddings and drift scores in `.canary/session.json`
- If `IBM_MOCK=true`, use mock embeddings without making API calls

### FR-8: Mock mode
- `IBM_MOCK=true` → skip IBM API calls, return deterministic mock embeddings
- Mock mode must produce realistic-looking output for demo purposes

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Latency | File change detection < 500ms after write |
| Portability | Pure Python 3.11+, no compiled dependencies |
| Install | `pip install canary-watch` or `git clone` + `pip install -r requirements.txt` |
| Config | `.canary.toml` in project root for thresholds and sensitive file patterns |
| Output | Rich terminal output with live progress bar using `rich` library |
| Storage | Session data stored in `.canary/` directory in the watched project |

---

## 7. Out of Scope for MVP

- GUI or web dashboard
- Network traffic inspection (agent HTTP calls)
- Multi-agent session tracking
- Cloud storage of session logs
- Integration with specific agent APIs (works as a filesystem-level watcher, agent-agnostic)

---

## 8. Success Metrics (Hackathon)

| Metric | Target |
|---|---|
| Prompt firewall demo | Paste a fake API key into a prompt, watch canary intercept it |
| File watchdog demo | Run an agent that touches `.env`, watch canary hard-stop it |
| Rollback demo | Show 5 files reverted cleanly with one command |
| Risk score bar | Colored progress bar visible and updating in real time |
| IBM integration | Granite embedding call in the critical path (file drift detection) |

---

## 9. Assumptions and Risks

| Assumption / Risk | Mitigation |
|---|---|
| IBM watsonx.ai credits may run low | Cache all embeddings by sha256; use IBM_MOCK for development |
| Filesystem watcher may miss rapid changes | Use `watchdog` library which uses OS-level inotify/FSEvents |
| Prompt interception requires the user to route prompts through canary | Document clearly; provide a wrapper command |
| Rollback may conflict with agent still running | Warn user to stop the agent before rolling back |
