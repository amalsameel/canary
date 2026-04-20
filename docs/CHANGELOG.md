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

---

## [2026-04-18 12:00] Model: Claude Opus 4.7 | Status: COMPLETED

### Completed this session
- Refined all five documentation files for full technical specificity before Claude Code execution
- Bumped PRD + ARCH to v0.3.0; README unchanged version; CHANGELOG appended; MASTERPROMPT tightened
- **Bug fixes baked into ARCH.md § code blocks:**
  - Fixed Click command naming bug in `cli.py` — `rollback_cmd` was registering as `canary rollback-cmd`; now uses `@cli.command("rollback")` explicit names for every command
  - Fixed infinite-loop bug in `watcher.py` — `.canary/` writes were triggering self-referential `on_modified` events; now explicitly ignored
  - Fixed privacy bug in baseline walk — `.env` and other sensitive files were being embedded through IBM; now filtered out of baseline entirely and never sent to any external API
  - Added per-path debouncing (300 ms) to prevent editor save-storms from firing multiple embedding calls
  - Added binary-file detection (null-byte sniff of first 1 KB) to prevent embedding PNGs, PDFs, compiled artifacts
  - Added 512 KB file-size cap to prevent massive logs from blowing through the embedding quota
  - Added Luhn check for credit card detection to kill false positives on arbitrary 13–16-digit numbers
  - Added entropy allowlist for git SHAs, UUIDs, and `sha256:` hashes
  - Added prompt-scan logging (count + severities, never raw match text) so the session log reflects the full firewall timeline
  - Added `IBM_REGION` env var with a region → host mapping (us-south, eu-de, jp-tok, eu-gb, au-syd)
  - Redaction shows only first 2 + last 2 chars (`sk***OP`) instead of the old `sk-a...yz` which leaked the first 4 chars
- **New modules added to ARCH.md:**
  - `canary/config.py` — loads `.canary.toml` with defaults for thresholds, ignore patterns, entry points, sensitive globs
  - `canary/binary.py` — binary-file detection
  - `canary/__init__.py` — declares `__version__ = "0.1.0"` so `canary --version` works
- **New test files added to ARCH.md § 16:**
  - `tests/test_firewall.py` — 10 pytest cases covering all secret types, Luhn, entropy allowlist
  - `tests/test_drift.py` — cosine similarity edge cases (identical, orthogonal, zero, empty)
  - `tests/test_sensitive_files.py` — glob matching for `.env`, `id_rsa`, `*.pem`
- **Other additions:**
  - `pyproject.toml` build system + pytest config
  - Top-level `.gitignore`
  - Auto-generated `.canary/.gitignore` so session data never leaks to git
  - Session log rotation at 10,000 events → timestamped archive file
  - `python_requires=">=3.10"` in setup.py
  - `tomli` dependency for Python 3.10 compatibility
- Refined MASTERPROMPT phases with explicit verification commands and expected outputs

### Left incomplete / known issues
- Still no code written — docs-only refinement pass
- IBM live-mode not yet exercised end-to-end
- `tests/fixtures/sample_project/.env` has to be created during Phase 4 scaffolding

### Next session should start with
- Read `docs/MASTERPROMPT.md` in full
- Read `docs/ARCH.md` cover-to-cover before writing any code
- Copy code blocks **verbatim** from ARCH.md — the fixes are baked in
- Set `IBM_MOCK=true` in `.env` and complete Phase 1–4 in mock mode before attempting live IBM calls in Phase 5+

### Files modified
- `docs/PRD.md` (refined, v0.2.0 → v0.3.0)
- `docs/ARCH.md` (refined, v0.2.0 → v0.3.0, ~20 modules specified verbatim)
- `docs/README.md` (refined, commands aligned with CLI, added troubleshooting)
- `docs/CHANGELOG.md` (appended this entry)
- `docs/MASTERPROMPT.md` (refined phase verification steps)

---

## [2026-04-18 17:45] Model: Claude Sonnet 4.6 | Status: COMPLETED

### Completed this session
- Implemented Phases 1–5 in full mock mode (IBM_MOCK=true)
- **Phase 1 — Project scaffold:** All directories, modules, stubs, setup.py, pyproject.toml, requirements.txt, .env.example, .canary.toml.example, .env (IBM_MOCK=true), venv (Python 3.11), `pip install -e .`. Verification passed: all 6 commands listed, version 0.1.0.
- **Phase 2 — Prompt firewall:** Real `prompt_firewall.py`, `risk.py`, `session.py`. All 11 firewall tests pass. Safe prompt → green 0% bar; leaky prompt → CRITICAL finding with sk***YZ redaction, 40% bar, confirmation prompt; --strict → exit 1; session.json records prompt_scan events.
- **Phase 3 — IBM Granite integration:** Real `ibm/iam.py`, `ibm/embeddings.py`, `drift.py`. Mock mode: len(v1)=768, v1 vs v3 drift=0.0000 (exact), v1 vs v2 drift>0. All 4 drift tests pass.
- **Phase 4 — Filesystem watchdog:** Real `watcher.py`, `checkpoint.py`. Sample project created. Baseline = 2 files (.env excluded). .env write → hard stop banner. auth.py change → drift alert. 12 writes @ 350ms spacing → change-rate alert. canary log shows drift_alert, modified, sensitive_file_access, change_rate_alert. Valid JSON output. .env never appears as modified event.
- **Phase 5 — Checkpoint and rollback:** canary rollback restores main.py to original. rollback_backup_<ts> created. canary checkpoints lists with timestamps. Rolling back to backup restores bad change (reversible). .canary/.gitignore exists with *.
- **Bug fixed (not in ARCH.md):** `watcher.py` calls `log_event()` without `target` argument — events were written to CWD instead of watched directory, breaking `canary log <target>`. Fixed all `log_event()` calls in `CanaryHandler` and `on_deleted` to pass `target=self.target`.

### Left incomplete / known issues
- Phase 6 (live IBM credentials) not started — waiting for credentials from developer
- ARCH.md §6 (watcher.py) has the `log_event` bug described above — the fix was applied in the actual code but ARCH.md was not modified (per rules)
- The change-rate alert test in MASTERPROMPT Phase 4 verification uses `for i in seq 1 12; do echo >> file; done` (no sleep), which with 300ms debounce would only generate 1 event. The actual test used `sleep 0.35` between writes to get 12 events. This is a spec/debounce tension worth noting.

### Next session should start with
- Activate `.venv/bin/activate` (Python 3.11 venv at canary/.venv)
- Begin Phase 6: update .env with real IBM_API_KEY, IBM_PROJECT_ID, IBM_REGION=us-south, IBM_MOCK=false
- Run `python scripts/test_embedding.py` to confirm live embeddings work
- Create demo_project/ (separate from tests/) for the hackathon demo
- Run through the 3-minute demo script from MASTERPROMPT §Phase 6

### Files modified
- `canary/__init__.py` (created)
- `canary/cli.py` (created, verbatim from ARCH.md §11)
- `canary/config.py` (created, verbatim from ARCH.md §14)
- `canary/mock.py` (created, verbatim from ARCH.md §12)
- `canary/binary.py` (created, verbatim from ARCH.md §13)
- `canary/sensitive_files.py` (created, verbatim from ARCH.md §8)
- `canary/prompt_firewall.py` (created, verbatim from ARCH.md §4)
- `canary/risk.py` (created, verbatim from ARCH.md §5)
- `canary/session.py` (created, verbatim from ARCH.md §10)
- `canary/drift.py` (created, verbatim from ARCH.md §7)
- `canary/checkpoint.py` (created, verbatim from ARCH.md §9)
- `canary/watcher.py` (created, verbatim from ARCH.md §6 + bug fix: log_event target arg)
- `canary/ibm/__init__.py` (created)
- `canary/ibm/iam.py` (created, verbatim from ARCH.md §3.1)
- `canary/ibm/embeddings.py` (created, verbatim from ARCH.md §3.2)
- `tests/__init__.py` (created)
- `tests/test_firewall.py` (created, verbatim from ARCH.md §16.2)
- `tests/test_drift.py` (created, verbatim from ARCH.md §16.3)
- `tests/test_sensitive_files.py` (created, verbatim from ARCH.md §16.4)
- `tests/fixtures/safe_prompt.txt` (created)
- `tests/fixtures/leaky_prompt.txt` (created)
- `tests/fixtures/sample_project/main.py` (created)
- `tests/fixtures/sample_project/auth.py` (created)
- `tests/fixtures/sample_project/.env` (created)
- `scripts/test_embedding.py` (created)
- `requirements.txt` (created, verbatim from ARCH.md §19)
- `setup.py` (created, verbatim from ARCH.md §20)
- `pyproject.toml` (created, verbatim from ARCH.md §21)
- `.gitignore` (created, verbatim from ARCH.md §22)
- `.env.example` (created, verbatim from ARCH.md §17)
- `.canary.toml.example` (created, verbatim from ARCH.md §18)
- `.env` (created, IBM_MOCK=true)

---

## [2026-04-18 20:53] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Finished the interrupted CLI polish pass so the app now has a consistent terminal UX across `prompt`, `watch`, `checkpoint`, `rollback`, `log`, `checkpoints`, and `mode`
- Added a persisted backend switch via `canary mode local|online|status`
- Made backend selection more robust by reading `IBM_MOCK` / `IBM_LOCAL` at call time in `canary/ibm/embeddings.py` instead of relying on import-time constants
- Added clearer local-model failure messages in `canary/local_embeddings.py` for missing optional packages or first-run model download problems
- Improved watchdog drift output with explicit `match` / `stable` / `review` / `alert` states so the diff-check flow is easier to read live
- Improved human-readable log output with compact event kinds and clearer labels
- Updated `docs/README.md` to match the actual CLI, including the new `mode` command, local/online backend guidance, and refreshed example output
- Made `scripts/test_local_granite.py` device selection portable (`mps`, `cuda`, then `cpu`)

### Verification run
- `python -m pytest -q` passes
- `canary --help` loads with the full command set
- `canary mode status`, `canary mode local`, and `canary mode online` all run cleanly
- `canary prompt "fix the login bug"` renders the new prompt-firewall output
- `python scripts/test_embedding.py` works in both local and online modes
- `canary watch tests/fixtures/sample_project` starts cleanly and shows the refreshed watchdog header/output

### Left incomplete / known issues
- `docs/ARCH.md`, `docs/MASTERPROMPT.md`, and `docs/PRD.md` still describe the earlier phased build contract rather than the newer post-build polish/features
- Local mode depends on optional packages (`transformers`, `torch`, `sentencepiece`) that are intentionally documented instead of being forced into base install requirements
- `.env` currently contains active developer-specific credentials/settings and should be treated as local-only

### Next session should start with
- If continuing product polish, decide whether the docs contract files (`ARCH.md`, `MASTERPROMPT.md`) should be updated to acknowledge `mode` / local Granite support
- If preparing a demo, create a fresh demo target directory and walk through `prompt`, `watch`, `log`, `checkpoints`, and `rollback` once in the selected backend mode

### Files modified
- `canary/cli.py`
- `canary/risk.py`
- `canary/watcher.py`
- `canary/ibm/embeddings.py`
- `canary/local_embeddings.py`
- `scripts/test_local_granite.py`
- `docs/README.md`
- `docs/CHANGELOG.md`

---

## [2026-04-18 21:17] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Refined prompt risk scoring so percentages are no longer just the same fixed pattern totals each time
- Added dynamic per-finding score boosts based on severity, finding type, matched token length, and token entropy
- Raised the effective score for exposed API keys and access tokens so they land in a clearly high-risk range
- Kept lower-sensitivity findings like email addresses meaningfully lower, so the prompt firewall has better spread across the risk scale
- Added tests to lock in the intended behavior:
  - API key findings score high
  - API key findings score higher than email-only findings
  - combining findings raises total risk

### Verification run
- `pytest tests/test_firewall.py -q` passes
- `pytest -q` passes (`21 passed`)
- Live prompt checks now show:
  - API key only → `71% high`
  - API key + email → `94% high`
  - email only → `23%`
  - inline password assignment → `49%`

### Left incomplete / known issues
- Prompt scoring is now more contextual, but it is still heuristic rather than model-based; there will always be some tuning tradeoff between consistency and interpretability

### Next session should start with
- If further tuning is needed, focus on prompt-firewall weighting in `canary/prompt_firewall.py`
- If the user wants even more nuanced scoring, consider adding contextual boosts for imperative language like "use this key", "deploy with", or "send to agent"

### Files modified
- `canary/prompt_firewall.py`
- `tests/test_firewall.py`
- `docs/CHANGELOG.md`

---

## [2026-04-18 21:37] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Removed the overly descriptive prompt-firewall copy so the interface reads more like a polished CLI and less like narrated assistant output
- Changed the prompt panel from `prompt scan` + `scanning for secrets, pii, and high-entropy strings` to a much shorter `prompt` + `checking prompt`
- Shortened the confirmation prompt from `send anyway?` to `continue?`
- Renamed the human-readable log label for `prompt_scan` events to `prompt review`
- Updated the README example output to match the cleaner prompt UX

### Verification run
- Live prompt check now renders:
  - title: `prompt`
  - subtitle: `checking prompt`
  - confirmation: `continue? [y/N]`

### Left incomplete / known issues
- Other command surfaces are already less verbose than before, but there is still room for another tone pass if the user wants the entire app even more minimal

### Next session should start with
- If more tone cleanup is needed, focus on the remaining watcher and rollback copy in `canary/cli.py` and `canary/watcher.py`

### Files modified
- `canary/cli.py`
- `docs/README.md`
- `docs/CHANGELOG.md`

---

## [2026-04-18 22:01] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Added installed wrapper commands so canary can gate prompts before they reach command-line coding agents
- Created `codex-safe`, `codex-exec-safe`, `claude-safe`, and `claude-print-safe`
- Wrapper flow now:
  - checks the initial prompt with canary
  - blocks automatically if findings are present
  - optionally starts a background `canary watch` sidecar with `--watch`
  - launches the requested agent only after the prompt clears
- Registered the new commands in `setup.py` console entry points
- Documented wrapper usage in `docs/README.md`

### Verification run
- Reinstalled the package in editable mode with:
  - `.venv/bin/pip install -e . --no-build-isolation`
- Wrapper help screens load:
  - `codex-safe --help`
  - `codex-exec-safe --help`
  - `claude-safe --help`
- `IBM_MOCK=true .venv/bin/codex-exec-safe --watch "fix the login bug" -- --help`:
  - gated the prompt
  - started a background watch
  - forwarded to `codex exec --help`
- `IBM_MOCK=true .venv/bin/claude-safe "fix the login bug"`:
  - gated the prompt
  - failed cleanly with `claude not found`

### Left incomplete / known issues
- These wrappers gate the initial prompt only; they do not intercept prompts typed later inside an interactive TUI session
- Forwarded agent flags should be passed after `--` so the wrapper can parse its own options cleanly

### Next session should start with
- If the user wants complete prompt interception for interactive sessions, build a PTY-based shim that sits between stdin and the agent TUI
- If the user wants shell convenience, consider adding example shell aliases/functions for zsh/bash startup files

### Files modified
- `canary/wrappers.py`
- `setup.py`
- `docs/README.md`
- `docs/CHANGELOG.md`

---

## [2026-04-19 02:18] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Restored the canary brand mark after the shared-header refactor flattened the UI into plain text titles
- Updated `canary/ui.py` so every header now renders a canary wordmark instead of a generic text-only label
- Tightened the home subtitle in `canary/cli.py` so the restored wordmark reads cleanly without duplicating `canary` in the panel body
- Refreshed the main README examples so the documented output matches the restored branded UI

### Verification run
- `.venv/bin/canary` now renders `◉ canary · home`
- `.venv/bin/canary prompt "fix the login bug"` now renders `◉ canary · prompt`
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- The shared wordmark is restored across the CLI, so future UI cleanup should preserve it instead of flattening the brand again

### Next session should start with
- If the user wants the logo pushed further, refine the home/watch layout around the shared wordmark instead of removing the mark from the header component

### Files modified
- `canary/ui.py`
- `canary/cli.py`
- `docs/README.md`
- `docs/CHANGELOG.md`

---

## [2026-04-19 02:29] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Restored the original multi-line ASCII canary logo as the main home-screen brand treatment
- Kept the lighter `◉ canary` wordmark in command headers so the everyday command surfaces stay clean while the app still opens with the full logo
- Wired the home screen to render the restored ASCII mark before the home panel

### Verification run
- `.venv/bin/canary` now opens with the full ASCII canary logo again
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- The README does not currently show the restored full home-screen logo, only the command examples

### Next session should start with
- If the user wants the docs fully aligned, add the restored home-screen logo to the README examples

### Files modified
- `canary/ui.py`
- `canary/cli.py`
- `docs/CHANGELOG.md`

---

## [2026-04-20 13:18] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- redesigned the shared terminal UI away from boxed panels and toward a lighter text-first layout with more whitespace, centered logo work, and softer separators
- rebuilt the protected launch surface used by `canary on` / `canary watch`:
  - it now uses the standalone block `C` mark derived from the main Canary wordmark so the launch screen branding matches the home screen logo
  - the surface now speaks in AI-agent language instead of repeatedly saying Claude for generic handoff states
  - added friendly slash commands inside the protected prompt flow: `/help`, `/status`, `/off`, and `/exit`
- reworked the pipeline handoff animation so it keeps the motion-heavy unicode flow but drops the framed panel styling
- removed the old “live audit panel” feel from `canary audit`:
  - audit now opens as a lightweight stream with a waiting spinner instead of a boxed surface
  - event detail lines were flattened so background and hook output no longer read like faux panels
- aligned the shared risk and result rendering with the new flatter CLI style so prompt reviews, watch output, and command summaries feel visually consistent
- refreshed the user-facing copy in the home screen, built-in docs, and README so the product speaks more generically about AI agents where appropriate while still preserving explicit Claude-only notes where they are technically necessary
- verified the change set locally:
  - `./.venv/bin/python -m py_compile canary/ui.py canary/cli.py canary/risk.py canary/watcher.py`
  - `./.venv/bin/python -m canary.cli`
  - `./.venv/bin/python -m canary.cli watch . --prompt "fix the login bug" --check-only`
  - `./.venv/bin/python -m canary.cli audit --idle 1`
  - `./.venv/bin/python -m canary.cli docs watch`
  - `./.venv/bin/python -m pytest -q` (`41 passed`)

### Left incomplete / known issues
- the protected watch flow still launches Claude specifically under the hood today because the watcher activation path depends on Claude hook/transcript signals; the copy is more generic now, but the technical dependency has not changed
- hidden maintenance commands and internal docstrings still mention Claude explicitly where they refer to the actual hook implementation

### Next session should start with
- if desired, add a true multiline prompt composer for the protected launch surface so the new visual design is matched by a richer editing experience
- if desired, explore a Codex-compatible watch activation path so the protected launch surface can become technically agent-agnostic rather than only visually agent-agnostic

### Files modified
- `canary/ui.py`
- `canary/cli.py`
- `canary/risk.py`
- `canary/docs_topics.py`
- `README.md`
- `docs/README.md`
- `docs/CHANGELOG.md`

---

## [2026-04-20 12:48] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- expanded direct guard interception beyond Claude so `canary guard install` now installs guarded launch shims for both `claude` and `codex` when those binaries are available in `PATH`
- generalized `canary.guard_shim` to dispatch per agent instead of hardcoding Claude, while still preserving one-shot `--ignore` and `--safe` behavior
- added Codex-aware prompt parsing for:
  - plain `codex "prompt"` launches
  - option-prefixed launches like `codex --search "prompt"`
  - non-interactive `codex exec "prompt"` runs, including cases with global options before `exec`
- changed the guarded handoff path to forward the original argv to the real agent binary after screening so Codex and Claude both keep their expected CLI behavior
- updated setup, guard install, and built-in docs so the CLI now describes `claude` + `codex` shims correctly while keeping Claude hooks as a separate capability
- added regression coverage for Codex guard install and Codex shim parsing, then re-ran the full suite successfully (`41 passed`)

### Left incomplete / known issues
- Codex currently gets launch-time prompt screening only; hook-based in-session prompt screening, transcript tailing, audit integration, and the protected watch launcher still depend on Claude-specific hooks and transcript files
- helper wrapper entrypoints are still not packaged as standalone commands; the supported path is installing the guarded shims into `~/.canary/bin`

### Next session should start with
- if desired, add a Codex-specific protected launch surface comparable to `canary watch` instead of keeping watch as a Claude-first workflow
- if desired, explore whether Codex exposes a stable local event or transcript surface that Canary can use for in-session auditing similar to Claude hooks

### Files modified
- `canary/guard_shim.py`
- `canary/wrappers.py`
- `canary/guard.py`
- `canary/cli.py`
- `canary/docs_topics.py`
- `tests/test_guard.py`
- `tests/test_guard_shim.py`
- `README.md`
- `docs/README.md`
- `docs/ARCH.md`
- `docs/PRD.md`
- `docs/CHANGELOG.md`

---

## [2026-04-20 12:24] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- finished the in-progress watch/audit polish pass left mid-flight in another session
- made the `canary watch` status presentation consistent with the newer pipeline direction:
  - kept the flowing unicode handoff animation with a moving `◈` pulse through the pipe segments
  - removed arrow-style separators from the static watch status row so the non-animated UI also reads like a pipeline instead of a stepper
- changed `canary audit` to foreground-first behavior:
  - `canary audit` now stays in the current terminal by default so Bash approval assessments can appear live while Claude waits for consent
  - `--background` now opts back into the older log + pid behavior instead of being the default mental model
  - refreshed audit copy so it explicitly tells users to run it in a second pane and explains that it tails Claude transcript JSONL files
- updated user docs and built-in docs topics to match the new foreground-first audit flow
- verified locally:
  - `./.venv/bin/python -m pytest -q` passes (`33 passed`)
  - `./.venv/bin/python -m canary.cli audit --help` shows the new `--background` option and live-first description
  - `./.venv/bin/python -m canary.cli audit --idle 1` runs in the foreground and exits cleanly after idle timeout
  - `./.venv/bin/python -m canary.cli watch . --prompt "fix the login bug" --check-only` renders the updated pipeline-style status panel

### Left incomplete / known issues
- background audit compatibility was not fully re-verified inside this sandbox because writing `~/.canary/audit.log` is blocked here; the foreground live path is the primary supported flow now
- multiline prompt composition inside the protected watch panel is still limited by the current single-line terminal input path
- an untracked `AGENTS.md` is present in the worktree and was left untouched

### Next session should start with
- if desired, replace the protected watch input with a fuller multiline TUI editor so the input experience matches the upgraded panel styling
- if desired, verify `canary audit --background` on a fully unsandboxed local shell and decide whether to keep or eventually hide that compatibility mode

### Files modified
- `canary/cli.py`
- `canary/ui.py`
- `canary/docs_topics.py`
- `README.md`
- `docs/README.md`
- `docs/ARCH.md`
- `docs/PRD.md`
- `docs/CHANGELOG.md`

---

## [2026-04-19 02:36] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Indented the restored ASCII canary logo by two spaces so it sits more comfortably in the terminal layout
- Integrated the logo directly into the home panel instead of rendering it as a detached splash above the UI
- Added a short product line under the logo inside the same home panel so the branding and the app framing read as one composed block

### Verification run
- `.venv/bin/canary` now shows the logo inside the `home` panel with the requested leading whitespace
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- Only the home screen uses the full ASCII logo; command screens still use the compact wordmark by design

### Next session should start with
- If the user wants even tighter branding, refine command-list spacing beneath the home panel or mirror the home treatment in docs output examples

### Files modified
- `canary/ui.py`
- `canary/cli.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 02:52] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Reworked the shared terminal UI to follow a flatter, more Claude-Code-like structure instead of rounded panels
- Added a split header pattern:
  - left-side canary mark or ASCII logo
  - right-side stacked metadata (`canary v0.1.0`, subtitle, path)
  - dark `> ...` command bar below
- Updated the core command surfaces to use that structure:
  - home
  - prompt
  - checkpoint
  - rollback
  - log
  - checkpoints
  - mode
  - watch
  - wrapper prompt gate
- Preserved canary’s own green accent while making the overall pacing, alignment, and command framing feel closer to the reference UI

### Verification run
- `.venv/bin/canary` renders the new flat home layout with logo + metadata + command bar
- `.venv/bin/canary prompt "fix the login bug"` renders the new prompt layout cleanly
- `.venv/bin/canary mode status` renders the new flat status layout
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- `docs/README.md` still shows older boxed examples and does not yet match the new flat layout
- The watch smoke test from this pass was checked visually before the final icon cleanup; the underlying watch flow was not otherwise changed

### Next session should start with
- Refresh the README examples to match the new flat UI if the user wants docs parity
- If the user wants even closer visual similarity, refine prompt/watch event spacing and risk sections around the new command-bar structure

### Files modified
- `canary/ui.py`
- `canary/cli.py`
- `canary/watcher.py`
- `canary/wrappers.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 02:58] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Shifted the canary ASCII logo block two additional spaces to the right so the first visible character aligns better in the flat home layout

### Verification run
- `.venv/bin/canary` now renders the logo with the requested extra leading whitespace
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- This was a spacing-only adjustment; no other UI behavior changed

### Next session should start with
- If more visual tuning is needed, continue from `canary/ui.py` and inspect the home render with `.venv/bin/canary`

### Files modified
- `canary/ui.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 03:03] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Shifted the top stroke of the block `C` in the canary logo two characters to the right to improve the silhouette/alignment

### Verification run
- `.venv/bin/canary` now renders the adjusted top stroke in the home logo
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- This was a shape-only tweak to the ASCII logo; no command layout or behavior changed

### Next session should start with
- If more logo tuning is needed, continue adjusting `LOGO` in `canary/ui.py` and verify with `.venv/bin/canary`

### Files modified
- `canary/ui.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 03:08] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Reverted the extra indentation on the top stroke of the block `C` in the canary logo

### Verification run
- `.venv/bin/canary` now renders the top row unindented again
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- This was a logo-shape reversal only; no other UI layout changed

### Next session should start with
- If more logo tuning is needed, continue adjusting `LOGO` in `canary/ui.py` and verify with `.venv/bin/canary`

### Files modified
- `canary/ui.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 03:11] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Restored the shifted top stroke of the block `C` in the canary logo after the prior reversal

### Verification run
- `.venv/bin/canary` now renders the top row in the shifted-right version again
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- This was a logo-shape restoration only; no other UI layout changed

### Next session should start with
- If more logo tuning is needed, continue adjusting `LOGO` in `canary/ui.py` and verify with `.venv/bin/canary`

### Files modified
- `canary/ui.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 03:15] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Kept the shifted top stroke of the block `C` in the canary logo
- Reverted the extra outer indentation on the full `C` by moving the overall logo block back left

### Verification run
- `.venv/bin/canary` now shows the top bar shifted while the overall `C` sits in the less-indented position
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- This was a logo-spacing adjustment only; no other UI behavior changed

### Next session should start with
- If more logo tuning is needed, continue adjusting `LOGO` and `logo_block()` in `canary/ui.py` and verify with `.venv/bin/canary`

### Files modified
- `canary/ui.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 03:29] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Removed the mock backend from the live runtime so only `local` and `online` modes remain
- Deleted `canary/mock.py`
- Simplified `canary/ibm/embeddings.py` to route only between on-device Granite and watsonx.ai
- Removed `IBM_MOCK` handling from the CLI mode switch and watcher mode label
- Removed `IBM_MOCK` from `.env` and `.env.example`
- Cleaned the public-facing docs and README surfaces so they no longer advertise mock/demo/fake backend behavior

### Verification run
- `.venv/bin/python -m py_compile canary/ibm/embeddings.py canary/cli.py canary/watcher.py canary/wrappers.py canary/local_embeddings.py` passes
- `.venv/bin/canary mode status` shows only `local` and `online`
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- Archived build/spec/history docs still contain historical references to the older mock/demo workflow:
  - `docs/ARCH.md`
  - `docs/MASTERPROMPT.md`
  - `docs/PRD.md`
  - older entries in `docs/CHANGELOG.md`
- I did not rewrite those historical records in this pass

### Next session should start with
- If you want a full archive purge as well, do a documentation-only rewrite of the historical/spec files listed above

### Files modified
- `canary/ibm/embeddings.py`
- `canary/cli.py`
- `canary/watcher.py`
- `.env`
- `.env.example`
- `README.md`
- `docs/README.md`
- `docs/CHANGELOG.md`

---

## [2026-04-19 03:40] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Simplified prompt findings output so it only shows severity and the category/description
- Removed the redacted matched-value column from the prompt findings table
- Shortened the clear state to just `clear`
- Removed `(semantic)` suffixes and `detected` phrasing from semantic findings so they read as plain categories
- Changed prompt confirmations to `continue? [y/n]`
- Changed the prompt review spinner text from `semantic review...` to `reviewing...`

### Verification run
- `.venv/bin/canary prompt "fix the login bug"` now shows just `clear`
- `printf 'n\n' | .venv/bin/canary prompt "my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ and my email john@example.com"` now shows findings without redacted values and prompts with `continue? [y/n]`
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- This was a presentation-only cleanup; detection logic and scoring behavior were not changed

### Next session should start with
- If more UI tone cleanup is needed, continue in `canary/risk.py`, `canary/semantic_firewall.py`, and prompt/watch confirmation copy

### Files modified
- `canary/risk.py`
- `canary/semantic_firewall.py`
- `canary/cli.py`
- `canary/wrappers.py`
- `canary/watcher.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 03:45] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Lowercased the finding descriptions in the prompt findings list
- Tightened the findings table spacing slightly so the block feels cleaner and less heavy

### Verification run
- `printf 'n\n' | .venv/bin/canary prompt "my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ and my email john@example.com"` now renders lowercase findings
- `.venv/bin/pytest -q` passes (`21 passed`)

### Left incomplete / known issues
- This was a styling-only adjustment to the findings block; risk scoring and detection behavior are unchanged

### Next session should start with
- If more tone cleanup is needed, continue refining `canary/risk.py` and the prompt/watch copy surfaces

### Files modified
- `canary/risk.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 02:00] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Reworked the terminal UI to feel more cohesive and more like a modern agent CLI: cleaner sequencing, tighter spacing, rounded headers, dim dividers, and a consistent canary-green accent throughout
- Added a shared UI layer in `canary/ui.py` so the visual style is reused instead of duplicated across commands
- Rebuilt `canary/cli.py` around the shared theme:
  - cleaner home screen
  - cleaner prompt flow
  - more structured rollback/mode/log/checkpoints screens
- Rebuilt `canary/watcher.py` startup and event output:
  - watch header now shows target + mode in a consistent frame
  - workspace indexing and checkpoint creation now read as a simple step sequence
  - live file events are cleaner and less noisy
- Updated `canary/risk.py` so findings/risk output fits the new style instead of the older mixed table/panel style
- Updated `canary/wrappers.py` so the wrapper handoff flow visually matches the core CLI

### Verification run
- `pytest -q` passes (`21 passed`)
- `canary prompt "fix the login bug"` renders the new prompt flow cleanly
- `printf 'n\n' | canary prompt "my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ fix things"` shows the new findings + risk layout and blocks cleanly
- `canary watch tests/fixtures/sample_project` starts with the new watch header and startup sequence
- `codex-safe --mode once --watch "fix the login bug" -- --help` uses the updated wrapper flow and forwards correctly

### Left incomplete / known issues
- `docs/README.md` examples still reflect older output styling and were not fully refreshed in this pass
- The wrappers still gate only the initial prompt, not follow-up prompts typed later inside an interactive agent TUI

### Next session should start with
- If the user wants the docs aligned, refresh the README examples to match the current CLI output
- If the user wants even closer parity with interactive agent TUIs, build a PTY-level prompt interceptor for follow-up prompts

### Files modified
- `canary/ui.py`
- `canary/cli.py`
- `canary/risk.py`
- `canary/watcher.py`
- `canary/wrappers.py`
- `docs/CHANGELOG.md`

---

## [2026-04-18 23:48] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Simplified the wrapper UX so interactive vs one-shot runs are now a toggle instead of separate primary commands
- `codex-safe` and `claude-safe` now accept:
  - `--mode interactive` (default)
  - `--mode once`
  - `--once` as a shortcut
- Removed the extra installed wrapper entry points from the main surface:
  - `codex-exec-safe`
  - `claude-print-safe`
- Updated the README examples to use the new toggle-based flow

### Verification run
- Reinstalled in editable mode with:
  - `.venv/bin/pip install -e . --no-build-isolation`
- Verified help output:
  - `.venv/bin/codex-safe --help`
  - `.venv/bin/claude-safe --help`
- Verified one-shot forwarding with:
  - `IBM_MOCK=true .venv/bin/codex-safe --mode once --watch "fix the login bug" -- --help`
- Confirmed the old wrapper binaries are no longer present in `.venv/bin`
- Full test suite still passes:
  - `pytest -q` → `21 passed`

### Left incomplete / known issues
- The wrapper still gates only the initial prompt; prompts typed later inside an interactive agent session are not intercepted

### Next session should start with
- If the user wants total prompt interception, build a PTY-based wrapper so every interactive input line passes through canary before reaching the agent

### Files modified
- `canary/wrappers.py`
- `setup.py`
- `docs/README.md`
- `docs/CHANGELOG.md`

---

## [2026-04-19 14:20] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- Turned Canary into a more installable package flow centered on a friendly post-install setup step:
  - base install stays lightweight with `pip install canary-watch`
  - `canary setup` now profiles the machine, recommends `local` or `online`, creates `.env` if needed, and can install/download local Granite support automatically
- Added hardware-aware local support logic:
  - new `canary/device.py` profiles CPU / memory / accelerator hints
  - new `canary/local_embeddings.py` detects missing local dependencies, installs them on demand, detects whether the Granite weights are already cached, and downloads them only with user approval
  - when local mode is forced on a weaker device, Canary warns that it may run exceptionally slower
  - when local mode is actually used on a weaker device, Canary emits the slower-device warning during runtime
- Added built-in docs via `canary docs`:
  - `install`
  - `setup`
  - `backends`
  - `guard`
  - `wrappers`
  - `watch`
- Added direct Claude Code / Codex guardrail integration:
  - new `canary guard install`
  - new `canary guard status`
  - new `canary guard remove`
  - new persistent shim config in `~/.canary/guard.json`
  - new `~/.canary/bin/{claude,codex}` shims that gate command-line prompts before forwarding them to the real agent CLIs
- Added runtime shim support:
  - new `canary/guard_shim.py` parses command-line prompt forms for `claude` and `codex`
  - prompt-bearing invocations are routed through the existing Canary review flow
  - non-prompt subcommands pass through untouched to the real binaries
- Refactored the wrapper commands so the safe wrappers and the direct shims share the same guarded-launch path
- Strengthened the public docs:
  - rewrote `README.md`
  - rewrote `docs/README.md`
  - documented the `PATH` export needed to activate direct shims
  - documented the hardware-aware install/setup flow
- Added tests for the new package/device/guard behavior:
  - `tests/test_device.py`
  - `tests/test_guard.py`
  - `tests/test_guard_shim.py`

### Verification run
- `python -m py_compile canary/cli.py canary/local_embeddings.py canary/wrappers.py canary/guard.py canary/guard_shim.py canary/device.py canary/docs_topics.py`
- `pytest -q` passes (`29 passed`)
- `canary docs`
- `canary docs guard`
- `canary mode status`
- `canary setup --prefer online --guards no`
- `canary guard status`
- `codex-safe --help`
- `claude-safe --help`
- `canary --help`

### Left incomplete / known issues
- Direct `claude` / `codex` shim integration guards prompts passed on the command line; prompts typed later inside an already-open interactive TUI are still outside Canary's interception path
- Installing local support from `canary setup` / `canary mode local` still depends on package index and model download availability at runtime

### Next session should start with
- If the user wants full interception of follow-up prompts typed inside an interactive agent session, build a PTY-level proxy so every entered prompt passes through Canary before reaching the agent
- If the user wants even smoother onboarding, add a dedicated install script or plugin-based shell integration that can place the shim directory in `PATH` automatically

### Files modified
- `canary/cli.py`
- `canary/device.py`
- `canary/docs_topics.py`
- `canary/guard.py`
- `canary/guard_shim.py`
- `canary/local_embeddings.py`
- `canary/wrappers.py`
- `.env.example`
- `README.md`
- `docs/README.md`
- `tests/test_device.py`
- `tests/test_guard.py`
- `tests/test_guard_shim.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 15:05] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- flattened the remaining visible cli copy to lowercase across the main surface
- updated `canary --help` to use lowercase help headings and help-option text:
  - `usage`
  - `options`
  - `commands`
  - `show the version and exit.`
  - `show this message and exit.`
- lowered the remaining mixed-case strings in:
  - setup / mode / guard / watch output
  - built-in docs topics
  - local / online runtime warnings
  - `.env.example` guidance comments

### Verification run
- `python -m py_compile canary/cli.py`
- `canary --help`
- `pytest -q` passes (`29 passed`)

### Left incomplete / known issues
- shell syntax and env var names such as `PATH`, `IBM_LOCAL`, and `IBM_PROJECT_ID` remain uppercase where case is required for correctness

### Next session should start with
- if the user wants the repo docs themselves fully restyled too, flatten the markdown prose in `README.md` and `docs/README.md` to the same lowercase voice

### Files modified
- `canary/cli.py`
- `canary/watcher.py`
- `canary/wrappers.py`
- `canary/docs_topics.py`
- `canary/local_embeddings.py`
- `canary/ibm/embeddings.py`
- `canary/ibm/iam.py`
- `.env.example`
- `docs/CHANGELOG.md`

---

## [2026-04-19 15:18] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- clarified the device-profile presentation so hardware labels use proper capitalization without changing the rest of the lowercase ui voice
- updated the live device summary to show:
  - `CPU`
  - `GB RAM`
  - `Apple Silicon`
  - `GPU`
- updated local backend labels that referenced `m1 gpu`

### Verification run
- `canary mode status`
- `pytest -q` passes (`29 passed`)

### Left incomplete / known issues
- the hardware detection is real system inspection, but the local-vs-online recommendation still uses Canary's threshold heuristic on top of that data

### Next session should start with
- if the user wants, expose the recommendation thresholds in config so the local/online choice policy is user-tunable

### Files modified
- `canary/device.py`
- `canary/cli.py`
- `canary/watcher.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 06:33] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- refreshed the user-facing docs to match the current repo instead of the older hackathon/spec wording
- rewrote `README.md` around the actual shipped cli surface:
  - repo-based install commands
  - claude-only guard integration
  - audit / watch / checkpoint flow
  - online vs local backend behavior
  - current limitations such as non-installed wrapper scripts
- updated `docs/README.md` to match the same current usage model
- replaced the old spec-style `docs/ARCH.md` with a concise architecture overview of the current runtime paths, storage locations, and module map
- replaced the old hackathon-style `docs/PRD.md` with a current-scope product document
- replaced the outdated phased build prompt in `docs/MASTERPROMPT.md` with a short note pointing future sessions at the real sources of truth
- expanded `canary/docs_topics.py` so `canary docs` now reflects the real commands and limitations in the codebase

### Verification run
- manually cross-checked the updated docs against:
  - `canary/cli.py`
  - `canary/guard.py`
  - `canary/guard_shim.py`
  - `canary/watcher.py`
  - `canary/local_embeddings.py`
  - `canary/ibm/embeddings.py`
  - `canary/ibm/generate.py`
- attempted runtime verification, but the local environment is missing installed cli dependencies such as `click` and `pytest`

### Left incomplete / known issues
- the package metadata still installs only `canary`; if standalone wrapper scripts are meant to be public, `pyproject.toml` still needs entrypoints for them
- hidden maintenance commands like `canary hook status` remain intentionally undocumented in most user-facing places

### Next session should start with
- if desired, align package metadata and console entrypoints with the new docs so install behavior is as polished as the documentation
- if desired, add a lightweight docs smoke test that checks `README.md` / `docs/README.md` command examples against `canary/cli.py`

### Files modified
- `README.md`
- `docs/README.md`
- `docs/ARCH.md`
- `docs/PRD.md`
- `docs/MASTERPROMPT.md`
- `canary/docs_topics.py`
- `docs/CHANGELOG.md`

---

## [2026-04-19 23:54] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- updated the markdown docs to match the current guarded-claude release flow:
  - `README.md` now documents the PyPI package name `canary-tool` and the installed `canary` CLI
  - `README.md`, `docs/README.md`, `docs/PRD.md`, and `docs/ARCH.md` now reflect hook-based in-session prompt screening through Claude `UserPromptSubmit`
- refreshed `canary/docs_topics.py` so `canary docs` stays aligned with the updated guard/screening behavior
- added an IBM watsonx.ai attribution notice to `LICENSE`
- validated the release locally:
  - `pytest -q` passes (`27 passed`)
  - installed missing `wheel` into `.venv`
  - built fresh release artifacts with `python -m build --sdist --wheel --no-isolation`
  - `twine check` passes for both the wheel and sdist

### Left incomplete / known issues
- GitHub push and PyPI upload have not been executed from this session yet
- `python -m build` with default isolated env bootstrap failed in the sandbox because it could not resolve package indexes; `--no-isolation` worked cleanly with the local virtualenv instead

### Next session should start with
- stage and commit the current release-ready tree
- push `main` to GitHub
- upload `/tmp/canary-release.LLAsH2/canary_tool-0.1.1.tar.gz` and `/tmp/canary-release.LLAsH2/canary_tool-0.1.1-py3-none-any.whl` with Twine once credentials are available

### Files modified
- `README.md`
- `docs/README.md`
- `docs/PRD.md`
- `docs/ARCH.md`
- `canary/docs_topics.py`
- `LICENSE`
- `docs/CHANGELOG.md`

---

## [2026-04-20 00:14] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- bumped the published package from `0.1.1` to `0.1.2` in:
  - `pyproject.toml`
  - `canary/__init__.py`
- fixed release packaging metadata so setuptools only includes the real application package:
  - narrowed package discovery to `canary` / `canary.*`
  - disabled namespace-package discovery for this repo
- diagnosed and worked around a stale local `build/` directory that was causing duplicate `build/lib/...` paths to leak into the wheel during release builds
- verified the final release artifacts:
  - `pytest -q` passes (`27 passed`)
  - `twine check` passes for both `canary_tool-0.1.2.tar.gz` and `canary_tool-0.1.2-py3-none-any.whl`
  - inspected the rebuilt wheel contents to confirm only `canary/...` package paths were present
- uploaded `canary-tool 0.1.2` to PyPI successfully

### Left incomplete / known issues
- the local `.env` stores the PyPI token as `PYPI_API_KEY = ...` with a space before `=`, which required custom parsing during upload; standard dotenv-style loading will be more reliable if it is changed to `PYPI_API_KEY=...`
- the old generated `build/` directory was moved to `/tmp/canary-build-backup-012c` during release cleanup

### Next session should start with
- commit and push the `0.1.2` version bump if the repo should reflect the published release immediately
- if desired, add an automated GitHub Actions publish workflow so future PyPI releases do not require manual Twine uploads

### Files modified
- `pyproject.toml`
- `canary/__init__.py`
- `docs/CHANGELOG.md`

---

## [2026-04-20 00:52] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- redesigned `canary watch` into a protected Claude launcher by default:
  - opens a compact terminal panel for a protected prompt
  - screens the prompt before any Claude handoff
  - shows a short unicode pipeline animation when the prompt is clear
  - starts the repository watcher in the background before launching Claude
  - preserves the older monitor-only behavior behind `canary watch --background`
- fixed the audit pipeline so pending Bash commands are visible before execution:
  - added Claude `PermissionRequest` hook support to the installed hook set
  - preserved `transcript_path`, `session_id`, and related metadata in Canary audit events
  - added `canary/claude_transcript.py` to tail Claude session JSONL files in `~/.claude/projects/`
  - updated `canary audit` to combine hook events with transcript-derived Bash intents and rejected permission results
- updated the watcher sidecar path in `canary/wrappers.py` so helper wrappers start the real watcher process directly instead of recursing through the new interactive `watch` command
- refreshed user-facing docs and built-in docs topics to match the new watch/audit behavior
- refreshed the live Claude integration on this machine with `./.venv/bin/python -m canary.cli guard install`, then verified all expected hooks are present in `~/.claude/settings.json`
- verified the change set locally:
  - `./.venv/bin/python -m pytest -q` passes (`33 passed`)
  - `./.venv/bin/python -m canary.cli watch --help` shows the new launcher/background options
  - `./.venv/bin/python -m canary.cli watch . --prompt "fix the login bug" --check-only` renders the new protected-launch flow cleanly
  - `./.venv/bin/python -m canary.cli hook status` shows `PreToolUse`, `PermissionRequest`, `PostToolUse`, and `UserPromptSubmit` Canary hooks all installed

### Left incomplete / known issues
- other machines with older Claude hook installs will still need `canary guard install` run again to add the new `PermissionRequest` hook and refresh any missing prompt hook entries
- the current Claude interactive-mode docs list transcript viewing under `Ctrl+O`; the earlier `Ctrl+T` note referenced during planning appears stale

### Next session should start with
- if desired, add an end-to-end demo or smoke test that exercises transcript-backed Bash auditing with a real Claude session fixture

### Files modified
- `canary/cli.py`
- `canary/ui.py`
- `canary/wrappers.py`
- `canary/claude_transcript.py`
- `canary/docs_topics.py`
- `tests/test_claude_transcript.py`
- `tests/test_cli_hooks.py`
- `README.md`
- `docs/README.md`
- `docs/ARCH.md`
- `docs/PRD.md`
- `docs/CHANGELOG.md`

---

## [2026-04-20 01:09] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- tightened the new `canary watch` launcher so the prompt surface feels much closer to Claude Code's docked terminal panel:
  - replaced the generic Rich panel with a bottom-docked dark panel centered around a `claude` header and muted terminal chrome
  - pushed the prompt UI toward the bottom of the terminal with large empty space above, matching Claude's sparse conversation-first layout
  - kept the watcher/audit status visible as compact pills instead of Canary-style stacked status cards
- polished the watch handoff flow:
  - the interactive prompt entry now renders inside the new docked panel flow
  - the safe-prompt animation now reuses the same Claude-like panel styling
  - `canary watch --prompt "...\" --check-only` now renders the same docked panel instead of falling back to a plain success line
- verified the updated UI pass:
  - `./.venv/bin/python -m canary.cli watch . --prompt "fix the login bug" --check-only` renders the new Claude-like panel
  - `./.venv/bin/python -m pytest -q` still passes (`33 passed`)

### Left incomplete / known issues
- the panel is intentionally a close terminal approximation built with Rich, not a byte-for-byte clone of Claude's proprietary TUI implementation
- multiline prompt composition inside the dock is still limited by the current terminal input approach; the interface is visually closer to Claude than the input engine is

### Next session should start with
- if desired, replace the current single-line input path with a fuller TUI input widget so multiline prompt editing matches the new panel styling more closely
- if desired, add a dedicated screenshot or asciinema-style demo artifact showing the new watch panel in action

### Files modified
- `canary/ui.py`
- `canary/cli.py`
- `docs/CHANGELOG.md`

---

## [2026-04-20 02:14] Model: Claude Sonnet 4.6 | Status: COMPLETED

### Completed this session
- Replaced simple block-C logo in `protected_prompt_panel` with the full `LOGO` constant (C glyph + pixelated "canary" text in brand green) for richer unicode presence
- Made `canary on` open the same Claude Code-style protected launch panel as `canary watch` (enable screening → interactive prompt → pipeline animation → Claude)
- Fixed `canary audit` transcript discovery:
  - Added `_discover_active_transcripts()` that scans `~/.claude/projects/**/*.jsonl` for files modified within the last 10 minutes
  - Audit listener now seeds transcript tails on startup (4 KB lookback to catch in-flight pending commands)
  - Periodic rescan every 5 s picks up new Claude sessions without needing a hook event to announce the path
- All 33 tests pass

### Files modified
- `canary/ui.py`
- `canary/cli.py`
- `docs/CHANGELOG.md`

---

## [2026-04-20 14:05] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- pushed the shared CLI visuals back toward a boxier retro style:
  - restored framed Rich surfaces with neon cyan / magenta accents, shaded unicode rails, and heavier boxed status cards
  - changed the protected launch input marker to `⎿ task` and reused `⎿` as the nested detail glyph across launch, audit, and status output
  - rebuilt the launch / handoff presentation around heavier panel chrome, nested signal-lane cards, and a more pulsing unicode pipeline animation
- upgraded prompt screening output:
  - `canary prompt`, guarded shims, and watch-screen prompt review now render inside the retro `PROMPT MATRIX`
  - added a dedicated risk-assessment panel whenever prompt risk reaches `35%` or higher
  - kept lower-risk prompts clean so the extra assessment card only appears when the score is materially elevated
- made the watch / audit flow more specific and less implementation-heavy:
  - the watch surface now shows the real handoff target (`claude code`) instead of generic “ai agent” copy
  - slash-help and launch status now explicitly tell users to open another terminal and run `canary audit`
  - removed the “under the hood” audit wording and replaced it with direct operational guidance
- updated user-facing docs and built-in docs to match:
  - README + docs/README now spell out the two-terminal audit workflow step by step
  - built-in `canary docs audit` and `canary docs watch` now tell users exactly when to open another terminal and when the risk-assessment panel appears
- added regression coverage for the new assessment threshold in `tests/test_risk.py`

### Left incomplete / known issues
- the retro surfaces are richer and more animated now, but the input path is still single-line terminal input rather than a full multiline TUI editor
- `canary watch` still launches Claude specifically today; the new UI makes that target explicit instead of pretending the launcher is fully agent-agnostic

### Next session should start with
- if desired, replace the current single-line protected prompt input with a fuller multiline editor so the retro launch surface has a matching input experience
- if desired, extend the same boxed retro treatment into more of the watcher event stream so drift/change alerts feel even closer to the launch surface styling

### Files modified
- `canary/ui.py`
- `canary/risk.py`
- `canary/cli.py`
- `canary/docs_topics.py`
- `README.md`
- `docs/README.md`
- `tests/test_risk.py`
- `docs/CHANGELOG.md`

---

## [2026-04-20 13:56] Model: GPT-5 Codex | Status: COMPLETED

### Completed this session
- replaced the current retro/neon terminal presentation with a simpler white-and-green visual system across the shared CLI surfaces
- rebuilt the protected `canary on` / `canary watch` experience into a unified command window:
  - the window now renders as one structured panel instead of the oversized launch box
  - the input line now reads as `task or /command` so plain tasks and Canary control commands share the same surface
  - the initial launch state stays branded, but the repeated command flow is intentionally compact
- added a live in-window slash-command palette for the command window:
  - typing `/` now filters matching commands in place
  - tab completes to the top match
  - the palette now routes core Canary actions like docs, usage, mode, guard, audit, watch, checkpoint, checkpoints, rollback, log, and setup without leaving the window
- simplified the loading/handoff presentation:
  - replaced the heavier boxed pipeline with a lighter structured loading panel
  - switched the motion to transforming unicode glyphs with pulsing text instead of the previous maximalist signal-lane treatment
- aligned prompt review and risk output with the new interface so prompt scans, usage, logs, and watch state all share the same minimal visual language
- updated user-facing docs and built-in docs to describe the unified command window and `/` palette
- added regression coverage for the launch-palette matching/completion helpers and re-ran the full suite successfully (`47 passed`)

### Left incomplete / known issues
- the live slash-command search only appears on true TTY terminals; the code falls back to the older line-input path when raw terminal input is unavailable
- the protected watch handoff is still Claude-first under the hood because the watch activation path depends on Claude-specific hook/transcript support

### Next session should start with
- if desired, add selection with arrow keys inside the command palette instead of top-match tab completion only
- if desired, promote more of the slash-command routing into dedicated reusable command handlers so the click command bodies and in-window actions share even more code

### Files modified
- `canary/ui.py`
- `canary/risk.py`
- `canary/cli.py`
- `canary/docs_topics.py`
- `README.md`
- `docs/README.md`
- `docs/ARCH.md`
- `tests/test_launch_palette.py`
- `docs/CHANGELOG.md`
