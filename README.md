# canary

Canary is a terminal safety layer for AI agent sessions. The default experience is now the `canary` shell itself: a persistent homescreen with screening on by default, slash commands for Canary controls, and a protected prompt lane that screens every handoff and asks before sending risky requests into a guarded agent launch.

Today, Canary is built around local IBM Granite plus protected `claude` and `codex` launch shims. Claude still has the deepest session integration because Canary can install Claude hooks, while `/audit` can tail compatible local transcript hints from both Claude and Codex during a live session.

## What Ships Today

- `canary` opens the interactive Canary shell.
- Plain text inside the shell is treated as a prompt and screened before handoff.
- A cleared shell prompt launches the selected AI agent inline in the current terminal by default. Set `CANARY_ALLOW_PARALLEL_TERMINALS=1` to prefer a second Terminal session on macOS.
- `/on` and `/off` toggle screening inside the shell, and `canary on` / `canary off` still work as direct commands.
- `canary guard install` installs protected `claude` / `codex` shims in `~/.canary/bin` when those binaries are available.
- Claude also gets prompt, permission, and tool hooks in `~/.claude/settings.json`.
- `/audit` and `/watch` now stay inside the main shell as live subprocess panels with `/audit exit` and `/watch exit`.
- When `/audit` is active and `tmux` is available, Canary can show audit beside the running agent in a split tmux session.
- `canary audit` now runs inline in the current terminal by default.
- `canary watch` opens a protected launcher, starts repo surveillance, creates checkpoints, and watches for risky drift without leaving the current terminal.
- `canary checkpoint`, `canary checkpoints`, `canary rollback`, and `canary log` manage snapshots and history, with named manual checkpoints required.
- `canary usage` now shows local Granite readiness for compatibility.

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

The PyPI package name is `canary-tool`, and the installed command is `canary`.

## Quick Start

Configure local IBM Granite and optional protected shims:

```bash
canary setup
canary guard install
export PATH="$HOME/.canary/bin:$PATH"
```

Launch the Canary shell:

```bash
canary
```

Inside the shell:

```text
/help
/audit
/watch
/checkpoint before-auth
fix the auth flow and explain the change
```

Inspect or restore a session afterward:

```bash
canary log .
canary checkpoints .
canary rollback .
```

## Shell Model

When you run bare `canary`:

- the header stays pinned at the top of the screen
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

Legacy compatibility commands like `canary prompt` and `canary mode` still exist, but they are no longer the main UX.

## Protected Agents

`canary guard install` does two things:

- installs protected launch shims such as `~/.canary/bin/claude` and `~/.canary/bin/codex`
- installs Claude hook commands in `~/.claude/settings.json` when Claude is present

That gives Canary two levels of protection:

- launch-time screening for guarded `claude` and `codex`
- deeper in-session coverage for Claude prompts, Bash permission requests, and selected tool events

The shims recognize:

- `-ignore` / `--ignore` to bypass screening once
- `-safe` / `--safe` to force screening once even if screening is off

## Local IBM Runtime

The redesigned shell now assumes local IBM Granite only.

- `canary setup` always prepares the local path when you do not choose explicitly
- `canary usage` reports local dependency and model-cache readiness
- there is no advertised hosted IBM fallback in the shell UX

Project-local config:

```env
IBM_LOCAL=true
# HF_HOME=~/.cache/huggingface
```

## Audit And Watch Flow

Typical protected workflow:

1. Run `canary setup` and `canary guard install`.
2. Export `~/.canary/bin` at the front of `PATH`.
3. Run `canary` and start working from the shell.
4. Use `/audit` when you want live Bash review in the shell. If `tmux` is available, Canary can keep audit visible beside the running agent in the same terminal window.
5. Use `/watch` or `canary watch .` when you want repo surveillance, checkpoints, and drift monitoring around a launch.
6. Use `/audit exit` and `/watch exit` to close those live subprocesses without leaving the shell.

`canary audit` reads Canary hook events plus compatible transcript hints from `~/.claude/projects/*.jsonl` and `~/.codex/sessions/**/*.jsonl`.

## Files Canary Writes

Project-local:

- `.canary/session.json`
- `.canary/checkpoints/`

Home directory:

- `~/.canary/guard.json`
- `~/.canary/audit.log`
- `~/.canary/watch.log`
- `~/.canary/audit_events.jsonl`
- `~/.canary/bin/claude`
- `~/.canary/bin/codex`

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
canary docs guard
canary docs usage
```

## Current Limitations

- The best in-session coverage is still Claude-specific because prompt and permission hooks are Claude-only.
- `codex` now shows up in `/audit` through transcript tailing, but it still does not have the same hook coverage as Claude.
- Bash auditing still uses local pattern rules instead of a local Granite chat model.
- The shell visuals are a terminal-native approximation, not a byte-for-byte clone of any proprietary TUI.

## Tests

```bash
pip install -e ".[dev]"
python3 -m pytest
```

## License

MIT
