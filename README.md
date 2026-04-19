# canary

Prompt firewall and filesystem watchdog for AI coding agents.

Canary sits between you, your agent, and your repo. It reviews prompts before they leave your machine, watches the workspace while the agent runs, and keeps rollback checkpoints ready if the session drifts.

## Install

Online-ready install:

```bash
pip install canary-watch
```

Local-capable install:

```bash
pip install "canary-watch[local]"
```

Then run the guided setup:

```bash
canary setup
```

`canary setup` is hardware-aware:
- on stronger laptops it recommends `local`
- on slower laptops it keeps you on `online`
- if you force `local` on a slower device, Canary warns that it may run exceptionally slower
- if local support is missing, Canary can install the packages and download the Granite model for you

## Quick start

Review a prompt:

```bash
canary prompt "fix the login bug"
canary prompt "my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ" --strict
```

Watch a repo:

```bash
canary watch .
```

Switch backends:

```bash
canary mode status
canary mode local
canary mode online
```

Work with checkpoints:

```bash
canary checkpoint .
canary checkpoints .
canary rollback .
canary log .
```

## Backends

Canary supports two backends only:

- `online` — Granite through IBM watsonx.ai
- `local` — Granite on-device through Hugging Face + `torch`

If you enable `local` on a weaker machine:
- Canary warns before switching
- Canary can install/download the local stack if you approve
- every local run warns that it will run exceptionally slower on that device

## Guided setup

Recommended:

```bash
canary setup
```

Useful variants:

```bash
canary setup --prefer auto
canary setup --prefer local
canary setup --prefer online
```

What setup does:
- creates `.env` if you do not have one yet
- profiles the machine
- chooses `local` or `online`
- installs local dependencies when needed
- downloads the local Granite model when needed
- can install direct `claude` / `codex` guard shims

## Built-in docs

Canary ships with built-in help topics:

```bash
canary docs
canary docs install
canary docs backends
canary docs guard
canary docs watch
```

## Direct Claude Code / Codex guardrails

Canary supports two integration styles.

### 1. Safe wrapper commands

```bash
claude-safe "refactor auth flow"
codex-safe "add tests for the payment module"
```

With workspace watch:

```bash
claude-safe --watch "fix the login bug"
codex-safe --watch "rewrite the api client"
```

One-shot mode:

```bash
claude-safe --mode once "summarize this repo"
codex-safe --mode once "review latest changes"
```

### 2. Direct CLI shims

Install direct guardrails in front of the real CLIs:

```bash
canary guard install
export PATH="$HOME/.canary/bin:$PATH"
```

Check status:

```bash
canary guard status
```

Remove them:

```bash
canary guard remove
```

This installs `claude` and `codex` shims in:

```text
~/.canary/bin
```

Put that directory at the front of `PATH` and command-line prompts sent to `claude` or `codex` will be checked before launch.

Important limitation:
- direct integration guards prompts passed on the command line
- prompts typed later inside an already-open interactive TUI are not intercepted yet

## Environment

Minimal `.env`:

```env
IBM_API_KEY=
IBM_PROJECT_ID=
IBM_REGION=us-south
IBM_LOCAL=false
```

For `online`, fill in the IBM values.

For `local`, use:

```bash
canary mode local
```

or:

```env
IBM_LOCAL=true
```

## Commands

```bash
canary prompt "<text>"
canary watch [path]
canary checkpoint [path]
canary checkpoints [path]
canary rollback [path] [checkpoint_id]
canary log [path]
canary mode [status|local|online]
canary setup
canary docs [topic]
canary guard install
canary guard status
canary guard remove
```

## Local performance

Local Granite is a good fit for:
- Apple Silicon Macs
- laptops with a discrete GPU
- higher-core machines with enough RAM

On slower CPU-only machines, Canary recommends `online`. If you choose `local` anyway, it will keep warning that local runs will be exceptionally slower.

## Tests

```bash
pip install "canary-watch[dev]"
pytest
```

## License

MIT
