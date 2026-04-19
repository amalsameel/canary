# canary user guide

This guide reflects the current codebase, not the earlier hackathon spec docs.

## Install

From the repo root:

```bash
pip install .
```

Optional extras:

```bash
pip install ".[local]"
pip install -e ".[dev]"
```

Only the `canary` CLI is installed by package metadata right now.

## Core Workflow

Set up the backend and optional Claude integration:

```bash
canary setup
```

Screen a prompt directly:

```bash
canary prompt "fix the login bug"
canary prompt "here is my key sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ" --strict
```

Install the guarded Claude shim:

```bash
canary guard install
export PATH="$HOME/.canary/bin:$PATH"
```

Start the background helpers for the next session:

```bash
canary audit
canary watch .
```

Inspect or restore the repo afterward:

```bash
canary log .
canary checkpoints .
canary rollback .
```

## Backends

Canary supports two runtime modes:

- `online` uses IBM watsonx.ai for Granite embeddings and Granite chat-based bash auditing
- `local` uses on-device Granite embeddings through Hugging Face + `torch`

Switch or inspect modes with:

```bash
canary mode status
canary mode local
canary mode online
```

`canary setup` and `canary mode local` profile the machine first and warn when local mode is likely to be slow.

## Claude Guardrails

`canary guard install` is currently Claude-only. It installs:

- a `claude` shim in `~/.canary/bin`
- audit and watch hooks in `~/.claude/settings.json`

The shim supports:

- `-ignore` / `--ignore` to bypass screening once
- `-safe` / `--safe` to force screening once

Limitation: prompts typed after Claude is already open are not intercepted yet.

## Command Surface

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

## Files Canary Writes

Project-local:

- `.canary/session.json`
- `.canary/checkpoints/`

Home directory:

- `~/.canary/guard.json`
- `~/.canary/usage.json`
- `~/.canary/audit.log`
- `~/.canary/watch.log`
- `~/.canary/audit_events.jsonl`

## Config

Use `.env` for backend settings:

```env
IBM_API_KEY=
IBM_PROJECT_ID=
IBM_REGION=us-south
IBM_LOCAL=false
```

Use `.canary.toml` to override watch thresholds, ignore lists, entry points, and sensitive-file patterns.
