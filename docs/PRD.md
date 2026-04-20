# canary current product scope

This document replaces the earlier hackathon-style PRD. It describes what the current codebase actually ships today.

## Product Statement

Canary is a terminal safety layer for AI coding sessions. In its current form it is Claude-first, but it can also intercept regular `codex` launches to screen prompts before handoff. Deeper in-session auditing, watching, and hook coverage still center on Claude Code workflows.

## Primary User

The current product is best suited for a developer who:

- runs Claude Code or Codex locally
- wants basic guardrails around prompt entry and tool execution
- wants repo-level drift monitoring and fast rollback
- is comfortable working entirely in the terminal

## Shipped Scope

### Prompt safety

- `canary prompt` scans prompt text before it is sent anywhere
- scans combine regex checks, entropy checks, path checks, disclosure keywords, and embedding-based semantic matches
- installed agent guardrails can screen launch-time prompts for both `claude` and `codex`
- installed Claude hooks can also screen in-session Claude prompt submissions
- `--strict` blocks automatically on any finding

### Agent launch safety

- `canary guard install` installs guarded `claude` and `codex` shims when those binaries are available
- `canary guard install` also installs Claude hook handlers in `~/.claude/settings.json`
- `canary on` / `canary off` toggle prompt screening for those shims
- one-shot overrides exist via `--ignore` and `--safe`

### Session audit

- `canary audit` listens for the next Claude session and renders risky tool activity in the current terminal by default
- pre-tool auditing covers `Bash`, `Write`, and `Edit`
- pending Bash approvals are read from Claude hook metadata and local transcript JSONL files
- post-tool output scanning covers `Bash` output for sensitive data exposure

### Repository watch and recovery

- `canary watch` opens a protected Claude launch panel by default and starts the watcher automatically after a clear prompt
- `canary watch --background` keeps the older monitor-only behavior
- it auto-indexes the workspace, creates a checkpoint, and tracks semantic drift
- sensitive filenames trigger an explicit warning path and are never embedded
- `checkpoint`, `checkpoints`, `rollback`, and `log` provide recovery and inspection

### Backend management

- `canary mode` switches between online IBM and local embeddings
- `canary setup` chooses a default mode based on hardware and can install agent guardrails
- `canary usage` shows daily soft usage tracking for online IBM calls

## Mode Behavior

### Online mode

Online mode uses IBM watsonx.ai for:

- Granite embeddings
- Granite chat-based bash auditing

It requires `IBM_API_KEY` and `IBM_PROJECT_ID` in `.env`.

### Local mode

Local mode uses Hugging Face + `torch` for on-device Granite embeddings.

It supports:

- semantic prompt scanning
- repo drift monitoring

It does not currently provide a local chat model for bash auditing, so those checks fall back to built-in pattern rules.

## Current Non-Goals

The current codebase does not ship:

- a web UI or dashboard
- multi-agent orchestration
- remote storage or central policy management
- standalone installed wrapper commands like `claude-safe`
- Codex in-session hooks or transcript-backed auditing

## Success Criteria For The Current CLI

The current repo should let a user:

1. Install `canary` from source.
2. Run `canary setup`.
3. Install guarded agent shims with `canary guard install`.
4. Screen prompts with `canary prompt` or through the guarded `claude` / `codex` shim.
5. Run `canary audit` and `canary watch .` during a Claude session.
6. Review session history with `canary log`.
7. Roll back with `canary rollback`.

## Near-Term Likely Extensions

The codebase is closest to expanding in these directions:

- broader agent support beyond guarded `claude` / `codex` launches
- stronger local-only auditing
- more polished packaging and installed entrypoints
