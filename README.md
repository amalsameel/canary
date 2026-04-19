# canary

Canary is a terminal safety layer for AI coding sessions. In the current codebase it is centered on Claude Code: it can review prompts, install a guarded `claude` shim, audit tool calls, watch a repo for risky drift, and keep checkpoints ready for rollback.

## What Ships Today

- `canary prompt` scans a prompt for secrets, PII, sensitive paths, and semantically similar confidential content before you hand it to an agent.
- `canary on` / `canary off` toggle prompt screening for installed Claude guard shims.
- `canary guard install` installs a guarded `claude` shim in `~/.canary/bin` and Claude hooks in `~/.claude/settings.json`.
- `canary audit` listens for risky Bash / Write / Edit activity from the next Claude session.
- `canary watch` waits for the next session, builds a file baseline, auto-creates a checkpoint, and monitors semantic drift and sensitive-file writes.
- `canary checkpoint`, `canary checkpoints`, `canary rollback`, and `canary log` manage snapshots and session history.
- `canary mode` switches between online IBM watsonx.ai and local on-device Granite embeddings.
- `canary usage` shows daily soft usage limits for IBM online generation and embeddings.

## Install

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

## Quick Start

Set up the backend and optional Claude integration:

```bash
canary setup
```

Review a prompt directly:

```bash
canary prompt "fix the login bug"
canary prompt "here is my key sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ" --strict
```

Install the Claude guard shim:

```bash
canary guard install
export PATH="$HOME/.canary/bin:$PATH"
```

Turn prompt screening on or off for guarded Claude launches:

```bash
canary on
canary off
```

Start the background auditor and repo watcher:

```bash
canary audit
canary watch .
```

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
canary audit [--idle 60] [--log] [--stop]
canary watch [path] [--idle 30] [--continuous] [--log] [--stop]
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

`canary hook status` and `canary hook remove` also exist, but they are hidden maintenance commands for the Claude hook wiring.

## Claude Integration

`canary guard install` does two things:

- installs a `claude` shim in `~/.canary/bin`
- adds Canary hook commands to `~/.claude/settings.json`

With the shim installed and `PATH` updated, command-line Claude prompts are screened before launch. The shim also recognizes:

- `-ignore` / `--ignore` to bypass screening for one call
- `-safe` / `--safe` to force screening for one call even if `canary off` is active

Current limitation: prompts typed after Claude is already open in an interactive TUI are not intercepted yet.

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
2. Start `canary audit` to capture risky tool activity from the next Claude session.
3. Start `canary watch .` to monitor the repo; it waits for the first hooked tool event, then indexes the workspace and creates a checkpoint.
4. Launch `claude "..."` through the shim.
5. Use `canary log`, `canary checkpoints`, and `canary rollback` if you need to inspect or restore the session.

`canary watch --continuous` skips the "next session" wait and watches immediately until you stop it.

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
- `audit_events.jsonl`
- `bin/claude`

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

- Direct guard installation is currently implemented for `claude` only.
- The packaged CLI entrypoint is `canary`; wrapper functions like `claude_safe` are present in the codebase but are not installed as standalone scripts.
- Interactive follow-up prompts typed inside an already-open Claude session are not screened.
- Local mode covers embeddings only; command auditing falls back to pattern rules instead of a local Granite chat model.

## Tests

```bash
pip install -e ".[dev]"
python3 -m pytest
```

## License

MIT
