"""Built-in documentation topics for `canary docs`."""

DOC_TOPICS = {
    "install": {
        "summary": "repo install commands and optional extras",
        "lines": [
            "  pip install .",
            "  pip install \".[local]\"",
            "  pip install -e \".[dev]\"",
            "",
            "  the package metadata currently installs the `canary` cli only.",
            "  use `.[local]` for on-device granite embeddings.",
        ],
    },
    "setup": {
        "summary": "guided backend setup and optional claude guard install",
        "lines": [
            "  canary setup",
            "  canary setup --prefer local",
            "  canary setup --prefer online",
            "  canary setup --guards yes",
            "",
            "  setup creates `.env` if needed, profiles the machine, selects a backend,",
            "  and can install claude guardrails when claude is available in PATH.",
        ],
    },
    "prompt": {
        "summary": "direct prompt review",
        "lines": [
            "  canary prompt \"fix the login bug\"",
            "  canary prompt \"my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ\" --strict",
            "",
            "  scans for secrets, pii, sensitive paths, and semantic matches",
            "  before you hand the text to an agent.",
        ],
    },
    "screening": {
        "summary": "toggle guarded claude prompt screening",
        "lines": [
            "  canary on",
            "  canary off",
            "",
            "  works with the installed claude shim from `canary guard install`.",
            "  use `--ignore` to bypass once or `--safe` to force screening once.",
        ],
    },
    "audit": {
        "summary": "background auditor for claude tool activity",
        "lines": [
            "  canary audit",
            "  canary audit --log",
            "  canary audit --stop",
            "",
            "  listens for risky bash / write / edit events from the next claude session.",
            "  online mode uses granite chat for bash auditing; local mode uses pattern rules.",
        ],
    },
    "watch": {
        "summary": "background repo watcher and drift monitor",
        "lines": [
            "  canary watch .",
            "  canary watch . --continuous",
            "  canary watch --log",
            "  canary watch --stop",
            "",
            "  waits for the next hooked session by default, then indexes the repo,",
            "  creates a checkpoint, and monitors semantic drift and sensitive-file writes.",
        ],
    },
    "checkpoints": {
        "summary": "snapshots, rollback, and session logs",
        "lines": [
            "  canary checkpoint . --name before-auth",
            "  canary checkpoints .",
            "  canary rollback .",
            "  canary log . --tail 20",
            "",
            "  checkpoints live under `.canary/checkpoints/` inside the target repo.",
            "  `rollback` creates a backup snapshot before restoring.",
        ],
    },
    "backends": {
        "summary": "online watsonx.ai vs local granite embeddings",
        "lines": [
            "  canary mode status",
            "  canary mode local",
            "  canary mode online",
            "",
            "  online mode uses ibm watsonx.ai for embeddings and command auditing.",
            "  local mode uses hugging face + torch for embeddings and warns on slow devices.",
        ],
    },
    "guard": {
        "summary": "direct claude code integration",
        "lines": [
            "  canary guard install",
            "  canary guard install --watch",
            "  canary guard status",
            "  canary guard remove",
            "  export PATH=\"$HOME/.canary/bin:$PATH\"",
            "",
            "  installs a guarded `claude` shim and claude settings hooks.",
            "  direct guard install is claude-only in the current codebase.",
        ],
    },
    "usage": {
        "summary": "daily soft limits for online ibm usage",
        "lines": [
            "  canary usage",
            "",
            "  tracks daily text-generation and embedding calls in `~/.canary/usage.json`.",
            "  override limits with CANARY_GENERATE_LIMIT and CANARY_EMBED_LIMIT.",
        ],
    },
}
