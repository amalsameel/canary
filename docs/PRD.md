# canary — Product Requirements Document

**Version:** 0.3.0
**Status:** Locked for MVP build
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

`canary` is a CLI watchdog for AI coding agent sessions. It inspects prompts before they reach the agent, monitors every file change the agent makes in real time using IBM Granite semantic embeddings, alerts the human when risk thresholds are crossed, and rolls back changes with one command if something goes wrong.

---

## 3. Target Users

- Developers using AI coding agents (Claude Code, Cursor, Devin) on codebases with secrets or compliance obligations
- Security engineers reviewing AI-assisted PRs
- Engineering leads at companies with SOX, HIPAA, or SOC 2 obligations
- Any developer who has ever accidentally pasted a secret into a chat window

---

## 4. Use Cases

### UC-1: Prompt firewall
Developer types a prompt that accidentally includes an API key. Before the prompt reaches the agent, canary intercepts it, highlights the sensitive data (redacted), shows a risk-score bar, and asks for confirmation.

### UC-2: Agent file watch
Developer runs `canary watch ./src` alongside Claude Code. The agent starts modifying files. Canary tracks every change semantically using IBM Granite embeddings and alerts when drift on any file exceeds the threshold.

### UC-3: Sensitive file access alert
The agent attempts to write to `.env` or `secrets.yaml`. Canary hard-stops and requires human confirmation before continuing. Sensitive files are **never embedded** through IBM — their contents are not sent to any external service.

### UC-4: Rollback
The agent has modified 23 files in a way that looks wrong. Developer runs `canary rollback` and all changes since the last checkpoint are reverted. The current state is backed up first, so the rollback is itself reversible.

### UC-5: Session replay
After a session, developer runs `canary log` to see a full timeline of what the agent did, what it read, what it changed, and what drift scores were recorded. `canary log --json` produces a machine-readable audit trail suitable for compliance review.

---

## 5. Functional Requirements

### FR-1: Prompt firewall
- Intercept the user's prompt before it is sent to the agent
- Scan for:
  - **Known-format secrets** (regex): `sk-`, `ghp_`, `ghs_`, `gho_`, `xox[baprs]-`, `AKIA`, `AIza`, `glpat-`, `hf_`, `rk_live_`, `sk_live_`, `pk_live_`
  - **High-entropy strings** (Shannon entropy > 4.5 over 20+ chars) with an allowlist for obvious non-secrets (UUIDs, git SHAs, base64 hashes following known prefixes like `sha256:`)
  - **PII**: email addresses, phone numbers, SSNs, credit card numbers (Luhn-validated to cut false positives)
  - **Sensitive paths**: `/etc/passwd`, `/etc/shadow`, `~/.ssh/`, `id_rsa`, `id_ed25519`, `id_dsa`, `.env` references, `/root/`
  - **Inline env assignments**: `API_KEY=...`, `SECRET=...`, `PASSWORD=...` with a value ≥ 8 chars
- On detection: print a redacted summary of each finding, compute a risk score, show a colored progress bar, and prompt for confirmation before proceeding
- `--strict` flag: exit with code 1 on any finding, no prompt
- Every scan logs a `prompt_scan` event to the session log with the finding count and score (never the raw secret)

### FR-2: Filesystem watchdog
- Watch a target directory recursively using OS-level events (`watchdog` → inotify/FSEvents/ReadDirectoryChangesW)
- **Debounce**: ignore repeat `on_modified` events for the same path within 300 ms (editor save storms)
- **Skip**: binary files, files > 512 KB, files inside ignored dirs (`.canary`, `.git`, `node_modules`, `__pycache__`, `venv`, `.venv`, `dist`, `build`)
- On every accepted change: compute IBM Granite embedding of the new content, compare against the sealed baseline via cosine similarity, record drift
- **Alert thresholds** (configurable in `.canary.toml`):
  - Files changed in 60 s > 10 → alert
  - Semantic drift on any single file > 0.15 → alert
  - Drift on entry-point file (`main.py`, `app.py`, `index.ts`, `index.js`, `server.py`, `__init__.py`) > 0.08 → alert
  - Any deletion → alert
  - Any write to a sensitive-file pattern (`.env*`, `*.key`, `*.pem`, `id_rsa`, `secrets.*`, `credentials.*`, `*.p12`, `*.pfx`, `*.keystore`, `*.jks`) → **hard stop** requiring `y` to continue

### FR-3: Sensitive-file guard (privacy boundary)
- Maintain a list of sensitive-file glob patterns (configurable)
- **Files matching these patterns are NEVER embedded** — their contents never leave the developer's machine
- On any create/modify event for a matching file: log the event and require interactive confirmation before the watcher proceeds (does not actually block the agent's write — the file is already on disk — but signals the human to intervene)
- Log every sensitive-file event regardless of user decision

### FR-4: Checkpoints and rollback
- On `canary watch` start: auto-create `checkpoint_<epoch>` (full snapshot of tracked files, excluding ignore patterns)
- `canary checkpoint [target]` creates a named checkpoint at any point
- `canary rollback [target] [checkpoint_id]` reverts all files to the specified (default: most recent) checkpoint
- Before rollback, the current state is snapshotted as `rollback_backup_<epoch>` — rollback is reversible
- `canary checkpoints` lists all snapshots with timestamps
- Checkpoints live in `<target>/.canary/checkpoints/`

### FR-5: Risk score and progress bar
- Compute a risk score 0–100 per event based on findings
- **Scoring table**:

| Finding | Points |
|---|---|
| Hardcoded secret in prompt (sk-, ghp_, AKIA, etc.) | +40 |
| PII: SSN | +40 |
| PII: credit card (Luhn-valid) | +30 |
| PII: email / phone | +20 / +10 |
| High-entropy string (not a known secret) | +25 |
| Sensitive file path reference in prompt | +25 |
| Private key file reference (`id_rsa`, etc.) | +40 |
| Sensitive file accessed at watch time | +25 |
| Critical file written at watch time | +40 |
| File drift > 0.15 | +20 per file |
| Entry-point drift > 0.08 | +25 |
| > 10 files changed in 60 s | +15 |
| File deletion | +30 |

- Final score is `min(sum(points), 100)`
- Display via `rich` as a 20-block progress bar:
  - 0–30: **green** `[████████░░░░░░░░░░░░] 38%`
  - 31–60: **yellow** `[████████████░░░░░░░░] 55%`
  - 61–100: **red** `[████████████████████] 89%`
- Numeric percentage shown alongside
- No verdict labels (CLEAN / RISKY / etc.) — the bar and color speak for themselves

### FR-6: Session log
- `canary log` prints a chronological timeline: prompt scans, file changes, alerts, checkpoints, rollbacks
- `canary log --json` produces valid JSON suitable for piping to `jq`
- `canary log --tail N` shows only the last N events
- Events stored in `<target>/.canary/session.json` as an append-only JSON array
- Maximum 10,000 events — older events rotate out to `session.YYYYMMDD.json`

### FR-7: IBM Granite semantic fingerprinting
- On session start, embed all non-sensitive, non-ignored, non-binary tracked files using IBM Granite (`ibm/granite-embedding-278m-multilingual` via watsonx.ai)
- Cache embeddings by `sha256(content)` to avoid redundant API calls
- On every accepted file change, re-embed and compute cosine similarity against the baseline
- Store all embeddings in an in-memory dict (session-lifetime only — not persisted, to avoid leaking content fingerprints to disk)
- `IBM_REGION` env var selects endpoint: `us-south` (default), `eu-de`, `jp-tok`, `eu-gb`, `au-syd`
- If `IBM_MOCK=true`, use seeded deterministic mock embeddings (768-dim, seeded by `sha256(content)`)

### FR-8: Mock mode
- `IBM_MOCK=true` → skip all IBM API calls, return deterministic 768-dim mock embeddings
- Mock mode must produce realistic output for demo (drift between different content must be > 0; drift between identical content must be 0)
- Used for development, CI, and demos without credentials

### FR-9: Configuration
- `.canary.toml` in the watched directory (or CWD) overrides defaults
- Missing file → built-in defaults used silently
- Supported keys: `thresholds.drift_alert`, `thresholds.drift_entry_point`, `thresholds.change_rate_window`, `thresholds.change_rate_limit`, `thresholds.max_file_size_bytes`, `entry_points.files`, `ignore.dirs`, `ignore.extensions`, `sensitive.patterns`

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Latency | File change detection < 500 ms after write (debounced to 300 ms per file) |
| Throughput | Baseline embedding of 100 files < 30 s with live IBM; < 1 s in mock mode |
| Portability | Pure Python 3.10+, no compiled dependencies |
| Install | `pip install -e .` after `git clone` |
| Config | `.canary.toml` in project root; falls back to built-in defaults |
| Output | Rich terminal output with colored progress bar using `rich` |
| Storage | Session data stored in `<target>/.canary/` with auto-generated `.gitignore` inside |
| Privacy | Sensitive-pattern files never sent to IBM; embeddings are session-memory only |

---

## 7. Out of Scope for MVP

- GUI or web dashboard
- Network traffic inspection of the agent's HTTP calls
- Multi-agent session tracking
- Cloud storage of session logs
- Integration with specific agent APIs (canary is filesystem-level and agent-agnostic)
- Prompt interception via stdin wrapper (documented as a future wrapper command)
- Signed / tamper-evident session logs

---

## 8. Success Metrics (Hackathon Demo)

| Metric | Target |
|---|---|
| Prompt firewall demo | Paste a fake `sk-abc123...` into a prompt, watch canary flag it with red bar and block |
| File watchdog demo | Run against a sample project; touch `.env`, watch canary hard-stop; modify `auth.py` with logic flip, watch drift bar update live |
| Rollback demo | Show 3+ files reverted cleanly with one command |
| Risk score bar | Colored progress bar visible and updating in real time during watch |
| IBM integration | Granite embedding call on the critical path (drift detection); caching demonstrated; mock mode available |
| Pitch length | 3-minute demo; no manual setup during presentation |

---

## 9. Assumptions and Risks

| Assumption / Risk | Mitigation |
|---|---|
| IBM watsonx.ai credits run low mid-demo | All embeddings cached by sha256; `IBM_MOCK=true` available as fallback |
| Filesystem watcher misses rapid changes | `watchdog` uses OS-level inotify/FSEvents; debounce prevents over-firing |
| Prompt interception requires user to route through canary | Documented clearly; `--strict` flag for CI integration |
| Rollback may conflict with agent still running | Warn user to stop agent first; rollback creates backup before restoring |
| Windows `watchdog` behavior differs from Linux/macOS | Demo performed on macOS/Linux; Windows marked as best-effort |
| Binary files (PNG, PDF) crash embedding | Binary detection via null-byte sniff of first 1 KB; skip |
| Huge files exceed embedding API limits | Skip files > 512 KB; embed only first 8 KB otherwise |
| `.canary/` dir triggers self-referential watch events | Explicitly ignored in watcher recursion |
