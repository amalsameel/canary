# canary architecture

This file describes the current shell-first architecture.

## System Overview

Canary now has four main runtime paths:

1. The interactive `canary` shell.
2. Protected launch shims for external agent CLIs such as `claude` and `codex`.
3. The audit stream for risky tool activity.
4. The repo watcher, checkpoint, and rollback pipeline.

The product is still terminal-local. There is no web service or separate backend app.

## 1. Interactive Shell

Bare `canary` launches the persistent shell in `canary/cli.py`.

The shell:

- forces screening on at startup
- keeps a pinned header rendered by `canary/ui.py`
- treats plain text as a prompt
- routes slash commands such as `/audit`, `/watch`, `/checkpoint`, and `/exit`
- uses animated surveillance and pipeline handoff states before launching a real agent

The UI layer for this shell lives primarily in:

- `canary/ui.py`
- `canary/cli.py`
- `canary/risk.py`

## 2. Protected Agent Shims

`canary guard install` writes protected launch shims into `~/.canary/bin`.

Relevant modules:

- `canary/guard.py`
  stores shim metadata and writes shim scripts
- `canary/guard_shim.py`
  receives shim launches, strips Canary flags, and forwards safe prompts
- `canary/wrappers.py`
  runs screening before handing control to the real agent binary

Current supported launch targets:

- `claude`
- `codex`

Claude still gets additional in-session coverage through hooks installed in `~/.claude/settings.json`.

## 3. Audit Stream

`canary audit` is now a shell-friendly audit launcher:

- by default it runs inline in the current terminal; set `CANARY_ALLOW_PARALLEL_TERMINALS=1` to prefer a second Terminal window on macOS
- if that fails, it falls back to inline streaming

The audit pipeline combines:

- Canary hook events written to `~/.canary/audit_events.jsonl`
- compatible Claude transcript hints from `~/.claude/projects/*.jsonl`
- compatible Codex transcript hints from `~/.codex/sessions/**/*.jsonl`

The relevant modules are:

- `canary/bash_auditor.py`
- `canary/claude_transcript.py`
- `canary/cli.py`
- `canary/prompt_firewall.py`

This is why the user-facing language is now more generic, but the deepest live translation still happens during Claude sessions because the hook layer is Claude-only.

## 4. Watch Pipeline

`canary watch` remains the protected launcher plus watcher path.

By default it:

- opens the protected prompt surface
- screens the prompt
- shows the unicode surveillance / pipeline animation
- starts the background repo watcher
- launches the resolved agent binary

The watcher runtime still lives in `canary/watcher.py`, with checkpoints in `canary/checkpoint.py` and event persistence in `canary/session.py`.

## Hosted IBM Default

The redesigned shell assumes hosted IBM watsonx.ai as the primary backend.

Used modules:

- `canary/ibm/iam.py`
- `canary/ibm/embeddings.py`
- `canary/ibm/generate.py`
- `canary/usage.py`

Local mode still exists through:

- `canary/local_embeddings.py`
- `canary/device.py`

But it is now a compatibility path rather than the primary UX.

## State And Files

Project-local:

- `.env`
- `.canary.toml`
- `.canary/session.json`
- `.canary/checkpoints/`

Home-directory:

- `~/.canary/guard.json`
- `~/.canary/bin/claude`
- `~/.canary/bin/codex`
- `~/.canary/audit.log`
- `~/.canary/watch.log`
- `~/.canary/audit_events.jsonl`
- `~/.canary/usage.json`

## Current Limitations

- Only Claude currently has in-session prompt and permission hooks.
- `codex` now has transcript-backed `/audit` visibility, but it still does not get the same hook coverage.
- Local mode still falls back to pattern-based Bash auditing instead of a local chat model.
- The shell UI is implemented with Rich, so it intentionally approximates a modern terminal TUI rather than reproducing a proprietary frontend byte-for-byte.
