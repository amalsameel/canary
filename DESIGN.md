# Canary TUI Design

This document describes the shell-first redesign of Canary in the style of the uploaded terminal references: a persistent framed header, a spacious prompt lane directly underneath it, minimal chrome, strong contrast, and animated unicode motion instead of dense widget panels.

## Design Target

The reference UI has three qualities Canary should emulate:

1. A persistent top header frame that feels like a home screen, not a transient splash.
2. A wide, breathable prompt strip below the header that behaves like the main control surface.
3. Lightweight live motion through unicode, shimmer, and line-based activity rows instead of heavy nested boxes.

Canary should feel like a protective command center for agent launches, not a generic CLI menu.

## Visual System

### Overall mood

- Background: deep charcoal terminal black.
- Primary accent: Canary greens, ranging from a soft stem green for frames to acid-lime for active states.
- Brand accent: acid-lime Canary green for activation, approval, and motion pulses.
- Body text: warm off-white, not pure terminal white.
- Secondary text: quiet stone gray.

The tone should feel watchful, atmospheric, and calm under pressure.

### Persistent header

The header is the only boxed region that remains on screen.

- Rounded or softly framed border in brand green.
- The full pixel Canary logo stretches across the top of the header.
- Under the logo:
  - current screening state
  - current launch target
  - current working directory
- At the bottom of the header:
  - `Getting started`
  - short command-oriented tips like `/help`, `/audit`, `/watch`

There is no `Recent activity` section in the redesign. This keeps the top surface cleaner and more distinctly Canary instead of echoing the exact reference layout.

## Input Surface

Below the header is a single full-width prompt lane inspired by the reference screenshots.

- A thin divider line above and below the input zone.
- The prompt prefix is a single leading symbol, starting as `❯`.
- When idle, the prompt strip is a dark neutral.
- After submission, the strip becomes a lighter graphite gray to indicate the request is “latched”.
- There must only be one real input surface on screen at a time.
- Shell behavior:
  - plain text is treated as a prompt
  - slash-prefixed entries are Canary commands

## Slash Command Model

The shell should feel command-complete without leaving the TUI.

Primary slash commands:

- `/help`
- `/status`
- `/on`
- `/off`
- `/audit`
- `/watch`
- `/checkpoint`
- `/rollback`
- `/log`
- `/checkpoints`
- `/docs`
- `/setup`
- `/guard`
- `/clear`
- `/exit`

Legacy one-shot commands such as `canary prompt` and `canary mode` remain compatibility paths, but they are not part of the main shell story.

## Motion Language

### Thinking / screening state

When a prompt is submitted:

- the leading `❯` becomes a fast cycling unicode spinner
- the submitted prompt remains visible in the lighter strip
- status text reads `Surveilling...`
- a shimmer or glimmer passes across that word every 1-2 seconds

### Subprocess rows

Under the thinking line, Canary renders lightweight subprocess rows similar to the reference activity list:

- one active row with a filled lime bullet
- queued rows with hollow muted bullets
- short descriptions such as:
  - `PromptFirewall("screening \"…\"")`
  - `SemanticScan("comparing anchors in …")`
  - `LaunchTarget("waiting to hand off into …")`

Each row should read like a live internal operation rather than a verbose paragraph.

### Pipeline handoff

Safe handoff animation should avoid arrows and instead use a signal pulse moving through a pipe.

Visual example:

```text
● shield ━━━━━◈━━━━━━━━━━━━ ○ watch ━━━━━━━━━━━━━━━ ○ codex
```

Rules:

- the moving signal is `◈`
- completed pipe sections fill in lime
- the active node uses a spinner frame
- pending nodes stay hollow and muted
- the entire sequence should feel like energy moving across a conduit, not menu progress bars

## Audit Experience

The audit UI should not become a boxed live panel.

Instead:

- by default `canary audit` opens inline in the current terminal
- set `CANARY_ALLOW_PARALLEL_TERMINALS=1` to prefer a second terminal on macOS
- that terminal shows a plain streamed transcript
- each event is rendered as compact text rows with timestamps, risk badges, and translated explanations
- risky pending Bash approvals should appear before execution when hook or transcript data is available

This keeps the primary shell breathable while still making audit feel live.

## Language Rules

User-facing copy should prefer generic “AI agent” phrasing unless a feature is truly Claude-specific.

Examples:

- say “launch target” or “AI agent” in the shell
- say “compatible transcript hints from `~/.claude/projects/`” where the implementation is actually Claude-specific
- reserve explicit `Claude` mentions for hook wiring, transcript sources, or hard technical limitations

## Frontend Architecture

The shell should be composed more like an app frontend than a pile of terminal print calls.

- one frontend command catalog defines:
  - slash command names
  - summaries
  - search keywords
  - header-tip ordering
- the shell input loop reads from that catalog for search and autocomplete
- the header renderer reads from the same catalog for the `Getting started` section
- app state should flow through reusable component-like renderers rather than duplicated string lists

This is the Python equivalent of the React/Ink mental model:

- state lives in one place
- renderers consume props/state
- command search, prompt chrome, and header tips are derived views of the same source of truth

## Backend Positioning

The redesigned shell assumes local IBM Granite only.

- `canary setup` should prepare the local Granite runtime
- `canary usage` can remain as a compatibility command, but it reports local readiness instead of hosted quota
- the main shell UX should not advertise a hosted IBM fallback

## Implementation Map

Primary implementation modules:

- `canary/cli.py`
  - shell loop
  - slash command routing
  - agent handoff
  - audit terminal launch
- `canary/ui.py`
  - persistent header frame
  - prompt strip
  - shimmer and surveillance animation
  - pipeline handoff animation
- `canary/risk.py`
  - flatter event rendering without stacked live panels
- `canary/guard.py`
  - protected shim installation for supported agents
- `canary/guard_shim.py`
  - launch-time screening handoff

## Success Criteria

The redesign is successful when:

- bare `canary` feels like a home screen and not a help dump
- the header stays visually stable across the session
- the prompt lane feels like the heart of the interface
- slash commands are memorable and discoverable
- animation creates motion and confidence without noise
- audit feels like a companion terminal, not a second dashboard
- the language reads as agent-generic by default while still being honest about Claude-specific internals
