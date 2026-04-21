# canary user guide

This guide reflects the current shell-first codebase.

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

## Core Workflow

Set up local IBM Granite and optional protected shims:

```bash
canary setup
canary guard install
export PATH="$HOME/.canary/bin:$PATH"
```

Launch the interactive shell:

```bash
canary
```

Inside the shell:

```text
/help
/audit
/watch
/checkpoint before-auth
review this repo and fix the auth flow
```

Inspect or restore the repo afterward:

```bash
canary log .
canary checkpoints .
canary rollback .
```

## Shell Behavior

- the header stays pinned at the top
- screening starts on automatically
- plain text is treated as a prompt
- slash commands control Canary itself
- `/setup` and `/guard` are available directly inside the shell

Primary slash commands:

```text
/on
/off
/audit
/audit exit
/watch
/watch exit
/checkpoint
/checkpoint before-auth delete
/rollback
/log
/checkpoints
/docs
/setup
/guard
/status
/clear
/exit
```

## Protected Agents

`canary guard install` can install protected `claude` and `codex` launch shims when those binaries are available. Claude also gets prompt, permission, and tool hooks through `~/.claude/settings.json`, while `/audit` can tail compatible local transcript hints from both Claude and Codex sessions.

## Local IBM Runtime

Local IBM Granite is the default path now.

- `canary setup` prepares the local runtime
- `canary usage` reports local dependency and model-cache readiness
- the shell no longer advertises a hosted IBM fallback

## Command Surface

```bash
canary
canary on
canary off
canary audit [--idle 60] [--log] [--stop]
canary watch [path] [--idle 30] [--continuous] [--prompt TEXT] [--check-only] [--background] [--log] [--stop]
canary checkpoint [path] --name NAME [--delete ID] [--delete-all]
canary checkpoints [path]
canary rollback [path] [checkpoint_id]
canary log [path] [--tail N] [--json]
canary setup [--prefer auto|local] [--guards auto|yes|no]
canary guard install [--watch]
canary guard status
canary guard remove
canary usage
canary docs [topic]
```

Legacy compatibility commands such as `canary prompt` and `canary mode` are still available, but they are no longer the main UX.

## Live Subprocesses

- `/audit` and `/watch` stay inside the main shell as live subprocess panels.
- Cleared prompt handoff launches the selected AI agent inline in the current terminal by default. Set `CANARY_ALLOW_PARALLEL_TERMINALS=1` to prefer a second Terminal session on macOS.
- If `tmux` is available, Canary can show `/audit` beside the running agent in a split tmux session.
- `/audit exit` and `/watch exit` close those subprocesses without leaving the shell.
- `/checkpoint <name>` creates a named snapshot, and `/checkpoint <name> delete` removes it inline.

## Files Canary Writes

Project-local:

- `.canary/session.json`
- `.canary/checkpoints/`

Home directory:

- `~/.canary/guard.json`
- `~/.canary/audit.log`
- `~/.canary/watch.log`
- `~/.canary/audit_events.jsonl`
- `~/.claude/projects/*.jsonl` for compatible Claude transcript hints
- `~/.codex/sessions/**/*.jsonl` for compatible Codex transcript hints

## Config

```env
IBM_LOCAL=true
# HF_HOME=~/.cache/huggingface
```

Use `.canary.toml` to override watch thresholds, ignore lists, entry points, and sensitive-file patterns.
