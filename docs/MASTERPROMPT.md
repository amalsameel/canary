# canary — Master Build Prompt

**For AI coding agents only.** Read this file in full before writing any code. Read `docs/ARCH.md` in full before writing any code. Read `docs/CHANGELOG.md` at session start.

---

## Contract with the developer

1. **ARCH.md code blocks are verbatim sources of truth.** When a phase says "copy from `docs/ARCH.md §N`", copy the code **exactly** — do not "improve", re-indent, re-name, or reorder. The bug fixes in v0.3.0 are already baked in; re-improving them will re-introduce bugs.
2. **Do not proceed to Phase N+1 until Phase N is verified.** Each phase has a verification section. If any verification check fails, stop and fix.
3. **Mock mode first.** Every phase is designed to be completable with `IBM_MOCK=true`. Only Phase 6 requires real credentials.
4. **Append to CHANGELOG on exit.** Whether the session finishes, is interrupted, or hits a wall, add an entry. Never modify a previous entry.

---

## Pre-session checklist (do this every time, no exceptions)

1. Read `docs/CHANGELOG.md` — find the most recent entry. If status is `INTERRUPTED` or `IN-PROGRESS`, resume from the "Next session should start with" bullet. If `COMPLETED`, move to the next phase.
2. Read `docs/ARCH.md` — understand the full module structure and all code blocks before touching anything.
3. Check `.env` exists. If not: copy from `.env.example` and stop. Ask the developer to either fill in `IBM_API_KEY` + `IBM_PROJECT_ID`, or set `IBM_MOCK=true`.
4. Before running anything that touches IBM, check that either (a) `IBM_API_KEY` and `IBM_PROJECT_ID` are set, or (b) `IBM_MOCK=true`. Never make real API calls without credentials.
5. Do NOT proceed to Phase N+1 until Phase N is verified working.

---

## Phase 1 — Project scaffold

**Goal:** `canary --help` runs without errors, all module stubs import cleanly.

### Steps

1. Create the full directory structure from `docs/ARCH.md §2` verbatim.

2. Create `requirements.txt` — copy from `docs/ARCH.md §19`.

3. Create `setup.py` — copy from `docs/ARCH.md §20`.

4. Create `pyproject.toml` — copy from `docs/ARCH.md §21`.

5. Create `.gitignore` (top-level) — copy from `docs/ARCH.md §22`.

6. Create `canary/__init__.py` — copy from `docs/ARCH.md §15`. This declares `__version__`.

7. Create `canary/mock.py` — copy from `docs/ARCH.md §12`.

8. Create `canary/binary.py` — copy from `docs/ARCH.md §13`.

9. Create `canary/sensitive_files.py` — copy from `docs/ARCH.md §8`.

10. Create `canary/config.py` — copy from `docs/ARCH.md §14`.

11. Create **stub files** for remaining modules so `cli.py` imports don't fail. Each stub file should import the dependencies it will eventually need, declare the public symbols as placeholders, and raise `NotImplementedError` if called. Stubs needed:
    - `canary/prompt_firewall.py` — stub `scan_prompt` and `PromptFinding`
    - `canary/risk.py` — stub `render_findings`, `render_risk_bar`, `compute_risk_score`
    - `canary/watcher.py` — stub `start_watch`
    - `canary/drift.py` — stub `cosine_similarity`
    - `canary/checkpoint.py` — stub `take_snapshot`, `rollback`, `list_checkpoints`
    - `canary/session.py` — stub `log_event`, `read_log`
    - `canary/ibm/__init__.py` (empty)
    - `canary/ibm/iam.py` — stub `get_iam_token`
    - `canary/ibm/embeddings.py` — stub `get_embedding`

12. Create `canary/cli.py` — copy from `docs/ARCH.md §11`. Stubs must exist first or imports fail.

13. Create `.env.example` — copy from `docs/ARCH.md §17`.

14. Create `.canary.toml.example` — copy from `docs/ARCH.md §18`.

15. Create `.env` by copying `.env.example` and setting `IBM_MOCK=true`:
    ```bash
    cp .env.example .env
    # then edit .env: IBM_MOCK=true
    ```

16. Install in editable mode:
    ```bash
    pip install -e .
    ```

### Verification ✓

Run:
```bash
canary --help
canary --version
```

Expected:
- `canary --help` lists **exactly these commands**: `prompt`, `watch`, `checkpoint`, `rollback`, `log`, `checkpoints`
- `canary --version` prints `canary, version 0.1.0`
- No import errors, no warnings about missing modules

If any command is named with dashes (e.g., `rollback-cmd`), you missed the explicit `@cli.command("rollback")` names — re-check `docs/ARCH.md §11`.

---

## Phase 2 — Prompt firewall

**Goal:** `canary prompt "text"` scans and shows findings with a risk score bar.

### Steps

1. Replace the `canary/risk.py` stub with the real module — copy verbatim from `docs/ARCH.md §5`.

2. Replace the `canary/prompt_firewall.py` stub — copy verbatim from `docs/ARCH.md §4`.

3. Replace the `canary/session.py` stub — copy verbatim from `docs/ARCH.md §10`. (The `prompt` command logs scans to the session file.)

4. Create test fixtures:

   `tests/fixtures/safe_prompt.txt`:
   ```
   Fix the bug in the login function where the session token expires too early.
   ```

   `tests/fixtures/leaky_prompt.txt`:
   ```
   Here is my OpenAI key sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ and my email john@example.com.
   Can you fix the auth bug?
   ```

5. Copy the three test files (`test_firewall.py`, `test_drift.py`, `test_sensitive_files.py`) verbatim from `docs/ARCH.md §16.2`, `§16.3`, `§16.4`. Also create `tests/__init__.py` (empty).

6. Run the firewall test suite:
   ```bash
   pytest tests/test_firewall.py -v
   ```
   All 10+ tests should pass.

7. Run all three demo prompts:
   ```bash
   canary prompt "Fix the bug in login"
   canary prompt "Here is my key sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ"
   canary prompt "Here is my key sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ" --strict
   ```

### Verification ✓

- Safe prompt → "✓ No sensitive data detected" + green bar at 0%
- Leaky prompt → at least one CRITICAL finding shown with redacted value (e.g., `sk***YZ`), red or yellow bar ≥ 40%, confirmation prompt appears
- `--strict` flag → exits with code 1 without prompting (check with `echo $?` after running)
- `cat .canary/session.json` shows at least one `prompt_scan` event

---

## Phase 3 — IBM Granite integration

**Goal:** Embeddings are computed and drift scores are calculated deterministically in mock mode.

### Steps

1. Replace the `canary/ibm/iam.py` stub — copy verbatim from `docs/ARCH.md §3.1`.

2. Replace the `canary/ibm/embeddings.py` stub — copy verbatim from `docs/ARCH.md §3.2`.

3. Replace the `canary/drift.py` stub — copy verbatim from `docs/ARCH.md §7`.

4. Create a manual test script at `scripts/test_embedding.py`:
   ```python
   import sys, os
   sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
   from dotenv import load_dotenv
   load_dotenv()
   from canary.ibm.embeddings import get_embedding
   from canary.drift import cosine_similarity

   v1 = get_embedding("def login(user): return True")
   v2 = get_embedding("def login(user): return False")
   v3 = get_embedding("def login(user): return True")

   print(f"len(v1)={len(v1)} (should be 768)")
   print(f"v1 vs v2 drift (should differ): {1 - cosine_similarity(v1, v2):.4f}")
   print(f"v1 vs v3 drift (should be 0): {1 - cosine_similarity(v1, v3):.4f}")
   ```

5. Run with mock mode:
   ```bash
   IBM_MOCK=true python scripts/test_embedding.py
   ```

6. Run the drift unit tests:
   ```bash
   pytest tests/test_drift.py -v
   ```

### Verification ✓

- `len(v1)` is `768`
- v1 vs v3 drift is **exactly 0.0000** (mock is deterministic, same input → same vector)
- v1 vs v2 drift is strictly greater than 0 (different input → different vector)
- All `test_drift.py` cases pass

---

## Phase 4 — Filesystem watchdog

**Goal:** `canary watch` detects file changes, flags sensitive-file access, and shows live drift scores — all in mock mode.

### Steps

1. Replace the `canary/checkpoint.py` stub — copy verbatim from `docs/ARCH.md §9`.

2. Replace the `canary/watcher.py` stub — copy verbatim from `docs/ARCH.md §6`.

3. Create the sample project at `tests/fixtures/sample_project/`:

   `tests/fixtures/sample_project/main.py`:
   ```python
   print("hello")
   ```

   `tests/fixtures/sample_project/auth.py`:
   ```python
   def check():
       return True
   ```

   `tests/fixtures/sample_project/.env`:
   ```
   API_KEY=fake_key_for_testing
   ```

4. Run the sensitive-files unit tests:
   ```bash
   pytest tests/test_sensitive_files.py -v
   ```

5. In **terminal A**, start the watcher:
   ```bash
   IBM_MOCK=true canary watch tests/fixtures/sample_project
   ```
   You should see "Checkpoint #0 created. Watching 2 files." (`.env` is not embedded — it's sensitive.)

6. In **terminal B**, simulate agent behavior one command at a time:

   **a. Trigger drift alert on `auth.py`:**
   ```bash
   echo "def check(): return not True  # security bypass" >> tests/fixtures/sample_project/auth.py
   ```
   Terminal A should show drift score and, if > 0.15, the red alert banner.

   **b. Trigger sensitive-file alert on `.env`:**
   ```bash
   echo "# accessed" >> tests/fixtures/sample_project/.env
   ```
   Terminal A should show "🚨 CANARY HARD STOP — Sensitive file modified: .env" and prompt for `y/N`. Type `n`.

   **c. Trigger change-rate alert:**
   ```bash
   for i in $(seq 1 12); do echo "# change $i" >> tests/fixtures/sample_project/main.py; done
   ```
   Terminal A should show the "files changed in 60s" alert at least once.

7. Stop the watcher with `Ctrl+C` in terminal A.

8. Inspect the session log:
   ```bash
   canary log tests/fixtures/sample_project
   canary log tests/fixtures/sample_project --json | head -40
   ```

### Verification ✓

- Baseline message says 2 files (not 3 — `.env` is excluded)
- `.env` write triggers the hard-stop banner with confirmation prompt
- `.env` contents are **never** passed to `get_embedding` (check by putting a breakpoint or print in `embeddings.py` if in doubt)
- `auth.py` write shows a drift score with bar
- 12 rapid writes to `main.py` triggers the change-rate alert
- `canary log` shows events of types: `modified`, `sensitive_file_access`, `drift_alert`, `change_rate_alert`
- `canary log --json` produces valid JSON (pipe through `jq` or `python -m json.tool`)
- No events of type `modified` have `.env` or `.canary/session.json` as the file — both must be filtered

---

## Phase 5 — Checkpoint and rollback

**Goal:** `canary rollback` cleanly reverts all changes.

### Steps

1. `canary/checkpoint.py` is already in place from Phase 4. Verify the CLI commands work end-to-end:

   ```bash
   # Reset the fixture to its original state first
   cat > tests/fixtures/sample_project/main.py <<< 'print("hello")'
   cat > tests/fixtures/sample_project/auth.py <<< $'def check():\n    return True'

   # Run watcher in background (or another terminal)
   IBM_MOCK=true canary watch tests/fixtures/sample_project &
   WATCH_PID=$!
   sleep 2

   # Make a "bad" change
   echo "# bad change from the agent" >> tests/fixtures/sample_project/main.py

   # Stop watcher
   kill $WATCH_PID
   wait $WATCH_PID 2>/dev/null

   # List checkpoints
   canary checkpoints tests/fixtures/sample_project

   # Roll back
   canary rollback tests/fixtures/sample_project

   # Verify main.py is restored
   cat tests/fixtures/sample_project/main.py
   ```

2. Test named checkpoint:
   ```bash
   canary checkpoint tests/fixtures/sample_project
   canary checkpoints tests/fixtures/sample_project
   ```

3. Test rollback-of-rollback (reversibility):
   ```bash
   # After the rollback above, a rollback_backup_<ts> should exist
   canary checkpoints tests/fixtures/sample_project
   # Roll back TO that backup — restores the "bad" change
   canary rollback tests/fixtures/sample_project rollback_backup_<ts>
   cat tests/fixtures/sample_project/main.py
   ```

### Verification ✓

- `canary rollback` restores `main.py` to `print("hello")` exactly
- A `rollback_backup_<timestamp>` directory appears in `.canary/checkpoints/`
- `canary checkpoints` lists all saved checkpoints with human-readable timestamps
- Rolling back to the backup restores the bad change (rollback is reversible)
- `.canary/.gitignore` exists and contains `*`

---

## Phase 6 — Live IBM + demo polish

**Goal:** Tool works end-to-end with real IBM credentials and is ready for a 3-minute pitch.

### Steps

1. Update `.env`:
   ```
   IBM_API_KEY=<your real key>
   IBM_PROJECT_ID=<your real project id>
   IBM_REGION=us-south
   IBM_MOCK=false
   ```

2. Re-run `scripts/test_embedding.py` with live mode:
   ```bash
   python scripts/test_embedding.py
   ```
   You should see v1 vs v2 drift that is a non-trivial positive number (typically 0.01 – 0.30 depending on content). v1 vs v3 drift should still be very close to 0 thanks to sha256 caching.

3. Create `demo_project/` as a clean, tidy project for the live demo (3–5 small Python files plus a `.env` containing a fake-looking secret). Do **not** reuse `tests/fixtures/sample_project/` — it has test cruft in `.canary/`.

4. Run through the demo script (below) at least twice with a timer. Make sure each step happens at or under its target time.

5. Update `docs/CHANGELOG.md` with an entry describing what was built.

### Checklist before pitching

- [ ] `.env` has real `IBM_API_KEY` + `IBM_PROJECT_ID`, and `IBM_MOCK=false`
- [ ] `canary prompt "my key is sk-abc123xyzDEFGHIJKLMNOP fix bug"` shows CRITICAL + yellow/red bar
- [ ] `canary watch demo_project` detects `.env` modification and hard-stops
- [ ] `canary watch demo_project` shows colored live drift bars as `auth.py` is modified
- [ ] `canary rollback demo_project` cleanly reverts test changes
- [ ] `canary log demo_project --json | head -20` produces valid JSON
- [ ] `canary --version` prints `canary, version 0.1.0`
- [ ] `pytest` passes all tests
- [ ] README screenshots match actual output

### Demo script (3 minutes)

**0:00–0:30 — Problem framing**
> "AI coding agents are now writing and modifying production code autonomously. Two things can silently go wrong: you accidentally leak a secret in your prompt, or the agent reads your `.env` file, modifies your auth logic, or rewrites 30 files you didn't ask it to touch. No existing tool catches either."

**0:30–1:00 — Prompt firewall demo**
```bash
canary prompt "my openai key is sk-abc123xyzDEFGHIJKLMNOP, fix the auth bug"
```
> "Canary intercepts the prompt before it reaches the model, flags the API key, shows the risk score, and blocks by default."

**1:00–2:00 — Watchdog demo**
```bash
# Terminal 1:
canary watch ./demo_project

# Terminal 2:
touch demo_project/.env                        # show hard stop
vim demo_project/auth.py                        # flip `True` to `not True`
```
> "IBM Granite embeds every file at session start — except sensitive ones, which never leave your machine. When the agent modifies `auth.py`, canary computes semantic drift. A one-word logic flip shows up as 0.18 drift in embedding space, even though a line diff would barely notice it. That's the detection that makes this meaningful."

**2:00–2:30 — Rollback demo**
```bash
canary rollback ./demo_project
cat demo_project/auth.py   # restored
```

**2:30–3:00 — Close**
> "Canary is agent-agnostic — works alongside Claude Code, Cursor, Devin, any agent that touches your filesystem. IBM Granite powers the semantic fingerprinting in the critical path. It's the last line of defense between an autonomous AI and your production codebase."

---

## CHANGELOG instructions (session-end)

At the end of every session, append a new block to `docs/CHANGELOG.md`:

```markdown
## [YYYY-MM-DD HH:MM] Model: <model-name> | Status: COMPLETED | INTERRUPTED | IN-PROGRESS

### Completed this session
- <bullet list>

### Left incomplete / known issues
- <bullet list>

### Next session should start with
- <specific instruction>

### Files modified
- <list>
```

**Never modify a previous entry. Only append.**
