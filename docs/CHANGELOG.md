# canary — Changelog

This file is maintained by AI coding agents. Every session must:
1. Read this file at the start of the session
2. Append an entry at the end of the session (whether completed or interrupted)
3. Never modify previous entries

---

## Format

```
## [YYYY-MM-DD HH:MM] Model: <model-name> | Status: COMPLETED | INTERRUPTED | IN-PROGRESS

### Completed this session
- ...

### Left incomplete / known issues
- ...

### Next session should start with
- ...

### Files modified
- ...
```

---

## [2026-04-18 00:00] Model: Claude Sonnet 4.6 | Status: COMPLETED

### Completed this session
- Pivoted project to canary — a two-way CLI watchdog for AI coding agent sessions
- Defined two core surfaces: prompt firewall (Human → Agent) and filesystem watchdog (Agent → Codebase)
- Added colored risk score progress bar (green/yellow/red) replacing verdict labels
- Created all five documentation files:
  - `docs/PRD.md` — full product requirements with 5 use cases, 8 functional requirements, risk table
  - `docs/ARCH.md` — full architecture with complete working code for every module: IBM Granite integration, prompt firewall, risk bar renderer, filesystem watchdog, drift, checkpoint/rollback, session log, CLI
  - `docs/README.md` — project README with demo output, quickstart, usage reference, IBM rationale
  - `docs/CHANGELOG.md` — this file
  - `docs/MASTERPROMPT.md` — 6-phase AI build execution plan with verification steps and demo script

### Left incomplete / known issues
- No code written yet — docs only
- IBM watsonx.ai credentials not yet verified
- `watchdog` library behavior on Windows may differ from Linux/macOS (use Linux/macOS for demo)

### Next session should start with
- Read `docs/MASTERPROMPT.md` and begin Phase 1 (project scaffold)
- Set `IBM_MOCK=true` in `.env` — do not attempt real IBM API calls until Phase 3
- Do NOT skip mock mode — it is required to make progress without live credentials

### Files modified
- `docs/PRD.md` (created)
- `docs/ARCH.md` (created)
- `docs/README.md` (created)
- `docs/CHANGELOG.md` (created)
- `docs/MASTERPROMPT.md` (created)
