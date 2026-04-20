# Canary TUI Redesign - Design Document

**Date:** 2026-04-20
**Topic:** Streamlined Terminal UI for Canary

---

## Overview

Redesign canary to be a streamlined, always-on TUI application with persistent header, shaded prompt area, subprocess tree display, and integrated pipeline/thinking indicator.

---

## Architecture

### Core Concept
- Running `canary` immediately enters interactive mode (no home screen)
- Prompt checking is **always on** by default
- `canary on/off` toggles screening state
- `exit` quits the session
- Only local Granite model (no IBM API key needed)

### Screen Layout
```
┌─────────────────────────────────────────┐
│  [CANARY LOGO]  v0.1.3                  │
│  /current/working/dir                   │
├─────────────────────────────────────────┤
│  > [prompt input area]                  │
│  ─────────────────────────────────────  │
├─────────────────────────────────────────┤
│  [subprocess tree with unicode]         │
│  ├── command 1                          │
│  └── command 2                          │
├─────────────────────────────────────────┤
│  ● thinking... [pipeline: scan→think]   │
└─────────────────────────────────────────┘
```

---

## Components

### Header Panel (Persistent)
- Canary ASCII logo on left
- Version number (v0.1.3)
- Current working directory
- Styled with brand green (#8DF95F) on dark surface (#171B21)
- Present throughout entire session

### Prompt Input Area
- Shaded/lighter background (#20262E) vs rest of screen (#171B21)
- `>` prefix marker
- Horizontal rules (─) above and below to visually constrain it
- Accepts typed input, `:command` syntax for internal commands

### Subprocess Tree
- Branch Unicode: `├──` for middle items, `└──` for last item, `│` for vertical connectors
- Each subprocess shows: `command_name [status]`
- Status indicators: ▶ (running), ✓ (complete), ✗ (failed)
- Scrollable if list gets long

### Pipeline + Thinking Indicator
- Two-state pipeline: `thinking` → `complete`
- Animated dot: ● pulses to ○ at ~2Hz while thinking
- Positioned at bottom of screen
- Appears only during active processing

### Command System
- `exit` - quit canary
- `on` - enable screening (default)
- `off` - disable screening
- `:help` - show commands
- `:status` - show current state
- `:clear` - redraw screen

---

## Data Flow

1. **Startup:**
   - Clear screen, render header
   - Load local Granite model (background)
   - Show prompt input area
   - Start input loop

2. **Input Handling:**
   - User types in prompt area
   - On Enter: submit prompt
   - On `:command`: execute internal command

3. **Prompt Processing:**
   - Show thinking indicator
   - Run local Granite scan
   - Display results in subprocess tree
   - Clear thinking indicator when done

4. **Subprocess Tracking:**
   - Each command gets a tree entry
   - Update status in real-time
   - Maintain scrollback of last N commands

---

## Error Handling

- **Model not loaded:** Show error in header, disable scanning
- **Invalid command:** Show error below prompt area, don't clear input
- **Screen resize:** Redraw on next frame
- **Keyboard interrupt (Ctrl+C):** Graceful exit

---

## Testing

- Test header persists across all states
- Test prompt area shading is visible
- Test subprocess tree renders correctly with varying depths
- Test thinking animation plays during processing
- Test pipeline state transitions
- Test exit command works from any state

---

## Migration Plan

1. Remove IBM API dependencies
2. Simplify CLI to single entry point
3. Create new UI layout components
4. Integrate subprocess tree
5. Add thinking/pipeline animation
6. Update command system
7. Remove deprecated commands (setup, mode, usage, etc.)
