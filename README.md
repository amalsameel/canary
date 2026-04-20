# canary

Canary is a terminal safety layer for AI coding sessions. In the current codebase it is Claude-first, but it can now intercept both `claude` and `codex` launches to screen prompts before they reach the real agent, while deeper in-session coverage remains centered on Claude Code.

## What Ships Today

- `canary prompt` scans a prompt for secrets, PII, sensitive paths, and semantically similar confidential content before you hand it to an agent.
- `canary on` / `canary off` toggle prompt screening for installed `claude` and `codex` guard shims.
- `canary guard install` installs guarded `claude` and `codex` shims in `~/.canary/bin` when those binaries are available, and also adds Claude session integration in `~/.claude/settings.json` for in-session protection.
- `canary audit` follows risky Bash / Write / Edit activity from the next supported agent session in the current terminal by default.
- `canary watch` opens a unified command window by default, then starts the watcher, builds a file baseline, auto-creates a checkpoint, and monitors semantic drift and sensitive-file writes.
- `canary checkpoint`, `canary checkpoints`, `canary rollback`, and `canary log` manage snapshots and session history.
- `canary mode` switches between online IBM watsonx.ai and local on-device Granite embeddings.
- `canary usage` shows daily soft usage limits for IBM online generation and embeddings.

## Install

From PyPI:

```bash
pip install canary-tool
```

From this repo root:

```bash
pip install .
```

Optional extras:

```bash
pip install ".[local]"
pip install -e ".[dev]"
```

`.[local]` adds the Hugging Face / `torch` stack used for local embeddings. The package metadata currently installs the `canary` CLI only.
The PyPI package name is `canary-tool`, and the installed command is `canary`.

## Quick Start

Set up the backend and optional AI agent integration:

```bash
canary setup
```

Review a prompt directly:

```bash
canary prompt "fix the login bug"
canary prompt "here is my key sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ" --strict
```

Install the guarded agent shims:

```bash
canary guard install
export PATH="$HOME/.canary/bin:$PATH"
```

Turn prompt screening on or off for guarded `claude` / `codex` launches:

```bash
canary on
canary off
```

Open the live safety feed in another terminal, then launch from your main terminal:

```bash
# terminal 2
canary audit

# terminal 1
canary watch .
```

Inside the Canary window, type `/` to search commands like `/docs`, `/usage`, `/guard`, `/watch`, `/checkpoint`, and `/mode` without leaving the same surface.

Inspect or restore a session:

```bash
canary log .
canary checkpoints .
canary rollback .
```

## Command Reference

```bash
canary prompt "<text>" [--strict]
canary on
canary off
canary audit [--idle 60] [--background] [--log] [--stop]
canary watch [path] [--idle 30] [--continuous] [--prompt TEXT] [--check-only] [--background] [--log] [--stop]
canary checkpoint [path] [--name NAME] [--delete ID] [--delete-all]
canary checkpoints [path]
canary rollback [path] [checkpoint_id]
canary log [path] [--tail N] [--json]
canary setup [--prefer auto|local|online] [--guards auto|yes|no]
canary guard install [--watch]
canary guard status
canary guard remove
canary mode [status|local|online]
canary usage
canary docs [topic]
```

`canary hook status` and `canary hook remove` also exist, but they are hidden maintenance commands for the Claude session integration.

## Agent Guard Integration

`canary guard install` does two things:

- installs `claude` and `codex` shims in `~/.canary/bin` when those binaries are present in `PATH`
- adds Claude session integration to `~/.claude/settings.json`

With the shims installed and `PATH` updated, launch-time prompts for both `claude` and `codex` are screened before the real binary starts, while preserving the original CLI argv that follows the prompt. With the Claude session integration enabled, prompts submitted from inside Claude are also screened, and `canary audit` can surface risky approvals and tool activity while that session is open. The shims also recognize:

- `-ignore` / `--ignore` to bypass screening for one call
- `-safe` / `--safe` to force screening for one call even if `canary off` is active

When a screened prompt scores `35%` or higher, Canary now adds a dedicated risk-assessment panel instead of only showing the raw meter.

## Backends

Canary has two runtime modes:

- `online`: IBM watsonx.ai for Granite embeddings and Granite chat-based bash auditing
- `local`: on-device Granite embeddings through Hugging Face + `torch`

Use:

```bash
canary mode status
canary mode local
canary mode online
```

`canary setup` and `canary mode local` both profile the machine first. On slower CPU-only devices, Canary warns before enabling local mode.

Important behavior difference:

- online mode uses IBM for embeddings and command auditing
- local mode still does semantic prompt scanning with local embeddings, but bash auditing falls back to built-in pattern rules because there is no local chat model wired in today

## Prompt, Audit, And Watch Flow

Typical guarded workflow:

1. Run `canary guard install` once and export `~/.canary/bin` at the front of `PATH`.
2. Open a second terminal window, tab, or split pane.
3. In that second terminal, run `canary audit` and keep it open.
4. In your main terminal, run your normal `claude "..."`, `claude -p "..."`, `codex "..."`, `codex exec "..."`, or `canary watch .` command.
5. If you use `canary watch .`, type the task at the `> task or /command` prompt in the unified Canary window.
6. Let Canary screen the prompt first; once the score hits `35%` or higher, the screen includes a risk-assessment panel before any handoff.
7. If the prompt is clear, Canary hands it off and keeps repo watch running in the background.
8. Use `canary watch . --background` if you want the old monitor-only behavior without launching the agent.
9. Use `canary log`, `canary checkpoints`, and `canary rollback` if you need to inspect or restore the session.

`canary watch --continuous` keeps the watcher running until you stop it. `canary audit --background` keeps the older log-backed mode if you still want it.

## Config

Project-local files:

```env
IBM_API_KEY=
IBM_PROJECT_ID=
IBM_REGION=us-south
IBM_LOCAL=false
```

- `.env` in the current working directory controls backend credentials and mode
- `.canary.toml` can override watch thresholds, ignore lists, entry-point files, and sensitive-file patterns

Online soft usage limits can be overridden with:

```bash
export CANARY_GENERATE_LIMIT=100
export CANARY_EMBED_LIMIT=300
```

## State And Logs

Canary writes project-local session data to:

- `.canary/session.json`
- `.canary/checkpoints/`

Home-directory state lives under `~/.canary/`, including:

- `guard.json`
- `usage.json`
- `audit.log`
- `watch.log`
- `bin/claude`
- `bin/codex`

## Built-In Docs

```bash
canary docs
canary docs install
canary docs setup
canary docs prompt
canary docs screening
canary docs audit
canary docs watch
canary docs checkpoints
canary docs backends
canary docs guard
canary docs usage
```

## Current Limitations

- The packaged CLI entrypoint is `canary`; wrapper functions like `claude_safe` are present in the codebase but are not installed as standalone scripts.
- In-session prompt screening, deeper audit coverage, and the protected watch launcher rely on Claude-specific session support. Codex currently gets launch-time prompt screening only.
- Local mode covers embeddings only; command auditing falls back to pattern rules instead of a local Granite chat model.

## Tests

```bash
pip install -e ".[dev]"
python3 -m pytest
```

## License

MIT
