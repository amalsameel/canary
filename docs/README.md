# canary user guide

## install

base install:

```bash
pip install canary-watch
```

local-capable install:

```bash
pip install "canary-watch[local]"
```

guided setup:

```bash
canary setup
```

## local vs online

canary supports two backends:

- `online` — ibm watsonx.ai
- `local` — on-device granite

`canary setup` and `canary mode local` both profile the machine before enabling local mode. On weaker devices, canary warns that local runs may be exceptionally slower and asks before continuing.

## built-in docs

```bash
canary docs
canary docs install
canary docs backends
canary docs guard
canary docs watch
```

## direct agent guardrails

safe wrapper commands:

```bash
claude-safe "refactor auth flow"
codex-safe "review the latest changes"
```

direct command shims:

```bash
canary guard install
export PATH="$HOME/.canary/bin:$PATH"
canary guard status
```

after `canary guard install`, put `~/.canary/bin` at the front of `PATH`.

## core commands

```bash
canary prompt "<text>"
canary watch .
canary checkpoint .
canary checkpoints .
canary rollback .
canary log .
canary mode status
canary mode local
canary mode online
```

## note

direct integration protects prompts passed on the command line. Prompts typed later inside an already-open agent TUI are not intercepted yet.
