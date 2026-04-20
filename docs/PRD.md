# canary current product scope

This document replaces the earlier hackathon-style PRD. It describes what the current codebase actually ships today.

## Product Statement

Canary is a terminal safety layer for AI coding sessions. In its current form it is focused on Claude Code workflows: screening prompts before and during guarded sessions, auditing risky tool use during a session, watching the repository for risky changes, and keeping rollback checkpoints ready.

## Primary User

The current product is best suited for a developer who:

- runs Claude Code locally
- wants basic guardrails around prompt entry and tool execution
- wants repo-level drift monitoring and fast rollback
- is comfortable working entirely in the terminal

## Shipped Scope

### Prompt safety

- `canary prompt` scans prompt text before it is sent anywhere
- scans combine regex checks, entropy checks, path checks, disclosure keywords, and embedding-based semantic matches
- installed Claude guardrails can screen both launch-time prompts and in-session Claude prompt submissions
- `--strict` blocks automatically on any finding

### Claude launch safety

- `canary guard install` installs a guarded `claude` shim
- `canary guard install` also installs Claude hook handlers in `~/.claude/settings.json`
- `canary on` / `canary off` toggle prompt screening for that shim
- one-shot overrides exist via `--ignore` and `--safe`

### Session audit

- `canary audit` listens for the next Claude session and renders risky tool activity
- pre-tool auditing covers `Bash`, `Write`, and `Edit`
- post-tool output scanning covers `Bash` output for sensitive data exposure

### Repository watch and recovery

- `canary watch` monitors a target directory during the next session or continuously
- it auto-indexes the workspace, creates a checkpoint, and tracks semantic drift
- sensitive filenames trigger an explicit warning path and are never embedded
- `checkpoint`, `checkpoints`, `rollback`, and `log` provide recovery and inspection

### Backend management

- `canary mode` switches between online IBM and local embeddings
- `canary setup` chooses a default mode based on hardware and can install Claude guardrails
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

- direct Codex guard installation
- a web UI or dashboard
- multi-agent orchestration
- remote storage or central policy management
- standalone installed wrapper commands like `claude-safe`

## Success Criteria For The Current CLI

The current repo should let a user:

1. Install `canary` from source.
2. Run `canary setup`.
3. Install the Claude guard with `canary guard install`.
4. Screen prompts with `canary prompt` or through the guarded `claude` shim.
5. Run `canary audit` and `canary watch .` during a Claude session.
6. Review session history with `canary log`.
7. Roll back with `canary rollback`.

## Near-Term Likely Extensions

The codebase is closest to expanding in these directions:

- broader agent support beyond Claude
- stronger local-only auditing
- more polished packaging and installed entrypoints
