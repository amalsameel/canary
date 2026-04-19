# canary architecture

This file describes the current codebase. It is an architecture overview, not a verbatim code-generation contract.

## System Overview

Canary currently has four main runtime paths:

1. Direct prompt review with `canary prompt`.
2. Claude Code prompt screening through an installed `claude` shim.
3. Background audit of Claude tool activity.
4. Background repository watching with checkpoints and rollback.

The product is centered on terminal workflows and local state. There is no web service or dashboard in the current codebase.

## Runtime Flow

### 1. Prompt Review

`canary prompt` runs two scanners:

- `canary/prompt_firewall.py`
  detects secrets, PII, sensitive file references, disclosure keywords, and high-entropy strings
- `canary/semantic_firewall.py`
  embeds the prompt and compares it against a small anchor set for semantically similar sensitive content

Findings are scored and rendered by `canary/risk.py`. Prompt scans are logged to `.canary/session.json` through `canary/session.py`.

### 2. Claude Guard Integration

`canary guard install` wires Canary into Claude Code in two places:

- `canary/guard.py` writes a `claude` shim to `~/.canary/bin/claude`
- `canary/cli.py` installs hook commands into `~/.claude/settings.json`

The shim launches `canary.guard_shim`, which:

- loads the stored guard config from `~/.canary/guard.json`
- strips one-shot flags like `--ignore` and `--safe`
- screens the initial command-line prompt when screening is enabled
- forwards the call to the real Claude binary

Important current boundary: this protects command-line prompts passed at launch time. Prompts typed after Claude is already open are not intercepted.

### 3. Audit Pipeline

The audit path is Claude-hook driven:

- `audit-hook` runs before `Bash`, `Write`, and `Edit`
- `watch-hook` runs after `Bash` to scan command output

These hooks append compact JSON lines to `~/.canary/audit_events.jsonl`.

`canary audit` is a background listener that tails those events and renders them in a readable terminal view. The relevant modules are:

- `canary/bash_auditor.py`
  audits bash commands
- `canary/prompt_firewall.py`
  scans pending write/edit content and bash output for sensitive material
- `canary/cli.py`
  owns hook installation, background listener management, and event rendering

Mode-specific behavior:

- online mode uses IBM Granite chat for bash-command auditing, with a pattern fallback on failure
- local mode skips remote chat calls and uses the pattern-based auditor directly

### 4. Watch Pipeline

`canary watch` starts a background watcher process. The underlying runtime lives in `canary/watcher.py`.

By default the watcher:

- waits for the next Claude hook event before activating
- indexes the target directory
- embeds non-sensitive text files into a baseline
- creates a checkpoint automatically
- monitors file changes until the idle timeout expires

In `--continuous` mode it skips the session wait and watches immediately until stopped.

The watcher behavior includes:

- per-path debounce for noisy editor save storms
- skip rules for ignored directories, binary files, and oversized files
- sensitive-file detection via filename globs from `canary/sensitive_files.py`
- semantic drift checks against the current baseline embedding
- change-rate alerts and deletion alerts
- session logging through `canary/session.py`

On macOS the watcher uses `PollingObserver` instead of a native FSEvents observer.

## Backends

### Online Mode

Online mode uses IBM watsonx.ai:

- `canary/ibm/iam.py`
  gets and caches IAM bearer tokens
- `canary/ibm/embeddings.py`
  calls Granite embeddings and caches vectors by content hash
- `canary/ibm/generate.py`
  calls Granite chat for bash auditing and caches responses

Soft daily usage limits are tracked by `canary/usage.py` in `~/.canary/usage.json`.

### Local Mode

Local mode is implemented in `canary/local_embeddings.py` and `canary/device.py`.

It provides:

- hardware-aware recommendations during setup
- optional dependency installation
- local Granite model download/loading through Hugging Face + `torch`
- runtime warnings on slower machines

Current limitation: local mode covers embeddings only. There is no local Granite chat path for bash auditing in this codebase.

## Checkpoints And Rollback

Checkpoint management lives in `canary/checkpoint.py`.

Capabilities:

- create named or automatic snapshots under `.canary/checkpoints/`
- list saved checkpoints
- delete one or all checkpoints
- rollback to the latest or a specific checkpoint
- create a backup snapshot before restoring, so rollback is itself reversible

## Config And State

### Project-local files

- `.env`
  backend mode and IBM credentials
- `.canary.toml`
  watcher thresholds, ignore lists, entry points, and sensitive patterns
- `.canary/session.json`
  append-only session log with rotation
- `.canary/checkpoints/`
  stored snapshots

### Home-directory files

- `~/.canary/guard.json`
- `~/.canary/bin/claude`
- `~/.canary/audit.log`
- `~/.canary/watch.log`
- `~/.canary/audit_events.jsonl`
- `~/.canary/usage.json`

## Module Map

- `canary/cli.py`
  main CLI entrypoint and background process management
- `canary/prompt_firewall.py`
  regex, entropy, and PII prompt scanning
- `canary/semantic_firewall.py`
  embedding-based prompt similarity checks
- `canary/risk.py`
  scoring and terminal rendering
- `canary/watcher.py`
  repo watch lifecycle and drift monitoring
- `canary/checkpoint.py`
  snapshot and rollback operations
- `canary/session.py`
  session event persistence
- `canary/guard.py`
  guard config and shim installation
- `canary/guard_shim.py`
  runtime shim entrypoint for guarded Claude launches
- `canary/bash_auditor.py`
  bash command risk analysis
- `canary/local_embeddings.py`
  local model loading and embedding generation
- `canary/ibm/*`
  watsonx.ai integrations
- `canary/usage.py`
  daily IBM usage tracking

## Current Limitations

- Direct guard installation is implemented for `claude` only.
- The package exposes only the `canary` CLI entrypoint; helper wrapper functions are not installed as standalone scripts.
- Interactive prompts typed inside an already-open Claude session are not screened.
- Local mode does not have a local chat model for command auditing.
