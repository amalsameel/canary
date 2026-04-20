# canary user guide

This guide reflects the current codebase, not the earlier hackathon spec docs.

## Install

From PyPI:

```bash
pip install canary-tool
```

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
The PyPI package name is `canary-tool`, and the installed command is `canary`.

## Core Workflow

Set up the backend and optional AI agent integration:

```bash
canary setup
```

Screen a prompt directly:

```bash
canary prompt "fix the login bug"
canary prompt "here is my key sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ" --strict
```

Install the guarded agent shims:

```bash
canary guard install
export PATH="$HOME/.canary/bin:$PATH"
```

Open the live safety feed in another terminal, then launch from your main terminal:

```bash
# terminal 2
canary audit

# terminal 1
canary watch .
```

Inside the Canary window, type `/` to search commands like `/docs`, `/usage`, `/guard`, `/watch`, `/checkpoint`, and `/mode`.

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

## Agent Guardrails

`canary guard install` installs:

- guarded `claude` and `codex` shims in `~/.canary/bin` when those binaries are available in `PATH`
- Claude session integration in `~/.claude/settings.json`
- in-session protection for Claude sessions

The shim supports:

- `-ignore` / `--ignore` to bypass screening once
- `-safe` / `--safe` to force screening once

With the shims installed, Canary screens launch-time prompts for both `claude` and `codex`, including `codex exec` when a prompt is provided. With the Claude session integration enabled, Canary also screens prompts submitted from inside Claude sessions, and `canary audit` can surface risky approvals and tool activity while that session is live.
Run `canary audit` in a second terminal pane for the intended live-assessment flow.
When a screened prompt reaches `35%` or higher, Canary also renders a risk-assessment panel.

## Command Surface

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

## Config

Use `.env` for backend settings:

```env
IBM_API_KEY=
IBM_PROJECT_ID=
IBM_REGION=us-south
IBM_LOCAL=false
```

Use `.canary.toml` to override watch thresholds, ignore lists, entry points, and sensitive-file patterns.
