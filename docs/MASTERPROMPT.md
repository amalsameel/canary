# canary — Master Build Prompt

**For AI coding agents only.** Read this file in full before writing any code.

---

## Pre-session checklist (do this every time, no exceptions)

1. Read `docs/CHANGELOG.md` — find the most recent entry. If status is `INTERRUPTED`, start where it left off. If `COMPLETED`, move to the next phase.
2. Read `docs/ARCH.md` — understand the full module structure and code before touching anything.
3. Check `.env` exists. If not, copy from `.env.example` and stop — ask the user to fill in credentials.
4. Check `IBM_MOCK=true` is set if IBM credentials are absent. Never make real API calls without credentials.
5. Do NOT proceed to Phase N+1 until Phase N is verified working.

---

## Phase 1 — Project scaffold

**Goal:** `canary --help` runs without errors.

### Steps

1. Create the full directory structure from `docs/ARCH.md §2` verbatim.

2. Create `requirements.txt` — copy from `docs/ARCH.md §14`.

3. Create `setup.py` — copy from `docs/ARCH.md §15`.

4. Create `canary/__init__.py` (empty).

5. Create `canary/mock.py` — copy from `docs/ARCH.md §12`.

6. Create stub files for every module (just `pass` bodies) so imports don't fail:
   - `canary/prompt_firewall.py`
   - `canary/watcher.py`
   - `canary/drift.py`
   - `canary/checkpoint.py`
   - `canary/risk.py`
   - `canary/sensitive_files.py`
   - `canary/session.py`
   - `canary/ibm/__init__.py`
   - `canary/ibm/iam.py`
   - `canary/ibm/embeddings.py`

7. Create `canary/cli.py` — copy from `docs/ARCH.md §11`. The CLI imports all modules so stubs must exist first.

8. Create `.env.example` — copy from `docs/ARCH.md §13`.

9. Install and verify:
```bash
pip install -e .
canary --help
```

### Verification ✓
- `canary --help` lists all commands: `prompt`, `watch`, `checkpoint`, `rollback`, `log`, `checkpoints`
- No import errors

---

## Phase 2 — Prompt firewall

**Goal:** `canary prompt "text"` scans a prompt and shows findings with a risk score bar.

### Steps

1. Create `canary/risk.py` — copy verbatim from `docs/ARCH.md §5`.

2. Create `canary/prompt_firewall.py` — copy verbatim from `docs/ARCH.md §4`.

3. Wire up the `prompt` command in `canary/cli.py` — it should already be wired from Phase 1; verify it calls `scan_prompt` and `render_findings`.

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

5. Test both:
```bash
canary prompt "Fix the bug in login"
canary prompt "Here is my key sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ"
canary prompt "Here is my key sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ" --strict
```

### Verification ✓
- Safe prompt: green bar at 0%, "No sensitive data detected"
- Leaky prompt: CRITICAL finding shown, red bar at 78%+, confirmation prompt appears
- `--strict` flag: exits with code 1 without prompting

---

## Phase 3 — IBM Granite integration

**Goal:** Embeddings are computed for files and drift scores are calculated.

### Steps

1. Create `canary/ibm/iam.py` — copy verbatim from `docs/ARCH.md §3.1`.

2. Create `canary/ibm/embeddings.py` — copy verbatim from `docs/ARCH.md §3.2`.

3. Create `canary/drift.py` — copy verbatim from `docs/ARCH.md §7`.

4. Write a quick manual test script `scripts/test_embedding.py`:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()
from canary.ibm.embeddings import get_embedding
from canary.drift import cosine_similarity

v1 = get_embedding("def login(user): return True")
v2 = get_embedding("def login(user): return False")
v3 = get_embedding("def login(user): return True")

print(f"v1 vs v2 (should differ): {1 - cosine_similarity(v1, v2):.4f}")
print(f"v1 vs v3 (should be ~0): {1 - cosine_similarity(v1, v3):.4f}")
```

5. Run with `IBM_MOCK=true` first, then with real credentials if available.

### Verification ✓
- `IBM_MOCK=true python scripts/test_embedding.py` runs without errors
- v1 vs v3 drift ≈ 0.0 (same text, deterministic mock)
- With real credentials: v1 vs v2 drift > 0 (meaning changed)

---

## Phase 4 — Filesystem watchdog

**Goal:** `canary watch ./tests/fixtures/sample_project` detects file changes and alerts on sensitive file access.

### Steps

1. Create `canary/sensitive_files.py` — copy verbatim from `docs/ARCH.md §8`.

2. Create `canary/session.py` — copy verbatim from `docs/ARCH.md §10`.

3. Create `canary/checkpoint.py` — copy verbatim from `docs/ARCH.md §9`.

4. Create `canary/watcher.py` — copy verbatim from `docs/ARCH.md §6`.

5. Create a sample project for testing:
```
tests/fixtures/sample_project/
├── main.py         (contains: print("hello"))
├── auth.py         (contains: def check(): return True)
└── .env            (contains: API_KEY=fake_key_for_testing)
```

6. In one terminal: `IBM_MOCK=true canary watch tests/fixtures/sample_project`

7. In another terminal, simulate agent behavior:
```bash
# Trigger drift alert
echo "def check(): return not True  # security bypass" >> tests/fixtures/sample_project/auth.py

# Trigger sensitive file alert
echo "# accessed" >> tests/fixtures/sample_project/.env

# Trigger change rate alert
for i in $(seq 1 12); do echo "# change $i" >> tests/fixtures/sample_project/main.py; done
```

### Verification ✓
- `.env` access triggers hard stop with confirmation prompt
- `auth.py` modification shows drift score and bar
- 12 rapid changes triggers change rate alert
- `canary log` shows all events after the session

---

## Phase 5 — Checkpoint and rollback

**Goal:** `canary rollback` reverts all changes cleanly.

### Steps

1. `canary/checkpoint.py` is already written from Phase 4. Verify the CLI commands work:

```bash
# Start fresh
IBM_MOCK=true canary watch tests/fixtures/sample_project &

# Make some changes
echo "# bad change" >> tests/fixtures/sample_project/main.py

# Stop watcher
kill %1

# Rollback
canary rollback tests/fixtures/sample_project

# Verify main.py is restored
cat tests/fixtures/sample_project/main.py
```

2. Test named checkpoint:
```bash
canary checkpoint tests/fixtures/sample_project
canary checkpoints    # should list the checkpoint
```

### Verification ✓
- `canary rollback` restores `main.py` to original content
- A `rollback_backup_<timestamp>` directory is created in `.canary/checkpoints/`
- `canary checkpoints` lists all saved checkpoints with timestamps

---

## Phase 6 — Demo polish

**Goal:** The tool is demoable in a 3-minute pitch with no loose ends.

### Checklist

- [ ] `IBM_MOCK=false` and real IBM credentials loaded in `.env`
- [ ] `canary prompt` with a fake API key shows CRITICAL + red bar
- [ ] `canary watch` detects `.env` access and hard stops
- [ ] `canary watch` shows live drift scores with colored bars as files change
- [ ] `canary rollback` cleanly reverts test changes
- [ ] `canary log --json` outputs valid JSON
- [ ] README is up to date
- [ ] `docs/CHANGELOG.md` has an entry for this session

### Demo script (3 minutes)

**0:00–0:30** — Problem framing
> "AI coding agents are now writing and modifying production code autonomously. Two things can silently go wrong: you accidentally leak a secret in your prompt, or the agent reads your .env file, modifies your auth logic, or rewrites 30 files you didn't ask it to touch. No existing tool catches either of these."

**0:30–1:00** — Prompt firewall demo
```bash
canary prompt "my openai key is sk-abc123xyzDEFGHIJKLMNOP, fix the auth bug"
```
> "Canary intercepts the prompt before it reaches the model, flags the API key, shows you the risk score, and blocks it until you confirm."

**1:00–2:00** — Watchdog demo
```bash
IBM_MOCK=false canary watch ./demo_project
# In another terminal: touch demo_project/.env
# Show hard stop
# Then: modify auth.py with a logic flip
# Show drift score bar update live
```
> "IBM Granite embeds every file at session start. When the agent modifies auth.py, canary computes semantic drift — not just a line diff, but a meaning diff. A logic flip that looks like a one-word change shows up as 0.18 drift."

**2:00–2:30** — Rollback demo
```bash
canary rollback ./demo_project
cat demo_project/auth.py   # restored
```

**2:30–3:00** — Close
> "Canary is agent-agnostic — it works alongside Claude Code, Cursor, Devin, any agent that touches your filesystem. It's the last line of defense between an autonomous AI and your production codebase."

---

## CHANGELOG instructions

At the end of every session, append to `docs/CHANGELOG.md`:

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

Never modify a previous entry. Only append.
