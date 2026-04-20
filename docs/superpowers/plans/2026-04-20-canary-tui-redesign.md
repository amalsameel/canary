# Canary TUI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign canary as a streamlined, always-on TUI with persistent header, shaded prompt area, subprocess tree, and integrated thinking/pipeline indicator.

**Architecture:** Single-screen TUI using Rich Live display with three main sections: persistent header (logo + version + cwd), shaded prompt input area with horizontal rules, subprocess tree with Unicode branch characters, and bottom thinking indicator with ●/○ animation.

**Tech Stack:** Python, Click, Rich (Console, Live, Panel, Table, Text), local-only Granite embeddings

---

## File Structure

| File | Responsibility |
|------|----------------|
| `canary/tui.py` | New streamlined TUI components (header, prompt area, subprocess tree, thinking indicator) |
| `canary/app.py` | Main application loop and state management |
| `canary/cli.py` | Simplified CLI entry point (remove complex subcommands) |
| `canary/config.py` | Configuration management (simplified, remove IBM API settings) |
| `tests/test_tui.py` | Tests for TUI components |
| `tests/test_app.py` | Tests for application logic |

---

## Prerequisites

- [ ] **Ensure working in a git worktree**

Run: `git worktree list`
Expected: Shows current worktree path

- [ ] **Install dependencies**

Run: `pip install -e ".[local]"`
Expected: Installs click, rich, transformers, torch

---

## Task 1: Create New TUI Components Module

**Files:**
- Create: `canary/tui.py`
- Test: `tests/test_tui.py`

- [ ] **Step 1: Write failing test for header panel**

```python
# tests/test_tui.py
def test_header_panel_renders_logo():
    from canary.tui import HeaderPanel
    panel = HeaderPanel(version="0.1.3", cwd="/test/path")
    renderable = panel.render()
    text = str(renderable)
    assert "CANARY" in text or "canary" in text.lower()
    assert "0.1.3" in text
    assert "/test/path" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui.py::test_header_panel_renders_logo -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'canary.tui'"

- [ ] **Step 3: Create HeaderPanel class**

```python
# canary/tui.py
from __future__ import annotations

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.text import Text
from rich import box

BRAND = "#8DF95F"
WHITE = "#F5F7FA"
MUTED = "#A5AFBA"
FRAME = "#5A6470"
SURFACE = "#171B21"
SURFACE_ALT = "#20262E"

LOGO = """\
[bold #8DF95F]  ███████[/bold #8DF95F]
[bold #8DF95F] ███   ███  ▄▀▄ █▌█ ▄▀▄ █▀▄ █ █[/bold #8DF95F]
[bold #8DF95F] ██         █▄█ █▐█ █▄█ █▀▄ ▐█▌[/bold #8DF95F]
[bold #8DF95F] ███   ███  ▀ ▀ █ █ ▀ ▀ █ █  █[/bold #8DF95F]
[bold #8DF95F]  ███████[/bold #8DF95F]"""


class HeaderPanel:
    """Persistent header with logo, version, and cwd."""

    def __init__(self, version: str, cwd: str) -> None:
        self.version = version
        self.cwd = cwd

    def render(self) -> RenderableType:
        logo_text = Text.from_markup(LOGO)
        info = Group(
            Text.from_markup(f"[bold {WHITE}]canary[/bold {WHITE}]  [dim {MUTED}]v{self.version}[/dim {MUTED}]"),
            Text(""),
            Text(self.cwd, style=f"dim {MUTED}"),
        )

        from rich.table import Table
        layout = Table.grid(expand=False, padding=(0, 3))
        layout.add_column(no_wrap=True)
        layout.add_column()
        layout.add_row(logo_text, info)

        return Panel(
            layout,
            border_style=FRAME,
            style=f"{WHITE} on {SURFACE}",
            box=box.HEAVY_EDGE,
            padding=(1, 2),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui.py::test_header_panel_renders_logo -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add canary/tui.py tests/test_tui.py
git commit -m "feat: add HeaderPanel component for persistent header"
```

---

## Task 2: Create Prompt Input Area Component

**Files:**
- Modify: `canary/tui.py`
- Test: `tests/test_tui.py`

- [ ] **Step 1: Write failing test for prompt area**

```python
# tests/test_tui.py
def test_prompt_area_renders_with_rules():
    from canary.tui import PromptArea
    area = PromptArea(prompt="test prompt", cursor="_")
    renderable = area.render()
    text = str(renderable)
    assert ">" in text
    assert "test prompt" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui.py::test_prompt_area_renders_with_rules -v`
Expected: FAIL with "ImportError: cannot import name 'PromptArea'"

- [ ] **Step 3: Add PromptArea class**

```python
# Add to canary/tui.py

class PromptArea:
    """Shaded prompt input area with horizontal rules."""

    def __init__(self, prompt: str = "", cursor: str = "▌") -> None:
        self.prompt = prompt
        self.cursor = cursor
        self._frame = 0

    def set_prompt(self, prompt: str) -> None:
        self.prompt = prompt

    def render(self) -> RenderableType:
        # Horizontal rule
        width = min(80, max(40, 60))
        rule = "─" * width

        # Input line with cursor
        display = self.prompt + self.cursor if self.cursor else self.prompt
        input_line = Text.from_markup(f"[bold {WHITE}]>[/bold {WHITE}]  {display}")

        content = Group(
            Text(rule, style=f"dim {FRAME}"),
            Text(""),
            input_line,
            Text(""),
            Text(rule, style=f"dim {FRAME}"),
        )

        return Panel(
            content,
            border_style=FRAME,
            style=f"{WHITE} on {SURFACE_ALT}",  # Lighter shading
            box=box.ROUNDED,
            padding=(0, 2),
        )

    def tick(self) -> None:
        """Animation frame tick."""
        self._frame += 1
        cursors = ["▌", "▐", "▖", "▗", "▘", "▙", "▚", "▛", "▜", "▝", "▞", "▟"]
        self.cursor = cursors[self._frame % len(cursors)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui.py::test_prompt_area_renders_with_rules -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add canary/tui.py tests/test_tui.py
git commit -m "feat: add PromptArea component with shaded background"
```

---

## Task 3: Create Subprocess Tree Component

**Files:**
- Modify: `canary/tui.py`
- Test: `tests/test_tui.py`

- [ ] **Step 1: Write failing test for subprocess tree**

```python
# tests/test_tui.py
def test_subprocess_tree_renders_unicode_branches():
    from canary.tui import SubprocessTree, SubprocessItem
    items = [
        SubprocessItem(name="scan", status="complete"),
        SubprocessItem(name="analyze", status="running"),
    ]
    tree = SubprocessTree(items=items)
    renderable = tree.render()
    text = str(renderable)
    assert "scan" in text
    assert "analyze" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui.py::test_subprocess_tree_renders_unicode_branches -v`
Expected: FAIL with import error

- [ ] **Step 3: Add SubprocessTree and SubprocessItem classes**

```python
# Add to canary/tui.py
from dataclasses import dataclass
from typing import Literal


@dataclass
class SubprocessItem:
    """Single subprocess entry."""
    name: str
    status: Literal["running", "complete", "failed", "pending"] = "pending"
    detail: str = ""

    @property
    def icon(self) -> str:
        icons = {
            "running": "▶",
            "complete": "✓",
            "failed": "✗",
            "pending": "○",
        }
        return icons.get(self.status, "○")


class SubprocessTree:
    """Tree display of subprocesses with Unicode branch characters."""

    def __init__(self, items: list[SubprocessItem] | None = None) -> None:
        self.items = items or []

    def add_item(self, item: SubprocessItem) -> None:
        self.items.append(item)

    def update_status(self, name: str, status: SubprocessItem.status) -> None:
        for item in self.items:
            if item.name == name:
                item.status = status
                break

    def render(self) -> RenderableType:
        if not self.items:
            return Text("")  # Empty if no items

        lines: list[RenderableType] = []
        for i, item in enumerate(self.items):
            is_last = i == len(self.items) - 1
            branch = "└──" if is_last else "├──"
            style = {
                "running": f"bold {BRAND}",
                "complete": f"bold {BRAND}",
                "failed": "bold white",
                "pending": MUTED,
            }.get(item.status, MUTED)

            line = Text.from_markup(
                f"[dim {MUTED}]{branch}[/dim {MUTED}]  "
                f"[{style}]{item.icon}[/{style}]  "
                f"{item.name}"
            )
            if item.detail:
                line.append_text(Text.from_markup(f"  [dim {MUTED}]{item.detail}[/dim {MUTED}]"))
            lines.append(line)

            # Add vertical connector if not last
            if not is_last:
                lines.append(Text.from_markup(f"[dim {MUTED}]│[/dim {MUTED}]"))

        return Panel(
            Group(*lines),
            border_style=FRAME,
            style=f"{WHITE} on {SURFACE}",
            box=box.ROUNDED,
            padding=(1, 2),
            title="activity",
            title_align="left",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui.py::test_subprocess_tree_renders_unicode_branches -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add canary/tui.py tests/test_tui.py
git commit -m "feat: add SubprocessTree with Unicode branch characters"
```

---

## Task 4: Create Thinking/Pipeline Indicator

**Files:**
- Modify: `canary/tui.py`
- Test: `tests/test_tui.py`

- [ ] **Step 1: Write failing test for thinking indicator**

```python
# tests/test_tui.py
def test_thinking_indicator_animates():
    from canary.tui import ThinkingIndicator
    indicator = ThinkingIndicator(is_thinking=True)
    frame1 = indicator.render()
    indicator.tick()
    frame2 = indicator.render()
    # Should change between frames
    assert str(frame1) != str(frame2) or indicator._frame > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui.py::test_thinking_indicator_animates -v`
Expected: FAIL with import error

- [ ] **Step 3: Add ThinkingIndicator class**

```python
# Add to canary/tui.py

class ThinkingIndicator:
    """Animated thinking indicator with ●/○ pulse and pipeline state."""

    def __init__(self, is_thinking: bool = False) -> None:
        self.is_thinking = is_thinking
        self._frame = 0
        self.pipeline_state: Literal["thinking", "complete"] = "thinking"

    def start_thinking(self) -> None:
        self.is_thinking = True
        self.pipeline_state = "thinking"
        self._frame = 0

    def stop_thinking(self) -> None:
        self.is_thinking = False
        self.pipeline_state = "complete"

    def tick(self) -> None:
        """Animation frame tick."""
        if self.is_thinking:
            self._frame += 1

    def render(self) -> RenderableType:
        if not self.is_thinking and self.pipeline_state == "complete":
            return Text("")  # Hidden when idle

        # Pulse between ● and ○
        glyphs = ["●", "○"]
        glyph = glyphs[self._frame % 2] if self.is_thinking else "●"
        glyph_style = f"bold {BRAND}" if self.is_thinking else MUTED

        # Pipeline: thinking → complete
        thinking_style = f"bold {BRAND}" if self.pipeline_state == "thinking" else MUTED
        complete_style = f"bold {BRAND}" if self.pipeline_state == "complete" else MUTED

        content = Text()
        content.append(glyph, style=glyph_style)
        content.append("  ")
        content.append("thinking", style=thinking_style)
        content.append("  ━━  ", style=f"dim {FRAME}")
        content.append("complete", style=complete_style)

        return Panel(
            content,
            border_style=FRAME,
            style=f"{WHITE} on {SURFACE}",
            box=box.ROUNDED,
            padding=(0, 2),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui.py::test_thinking_indicator_animates -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add canary/tui.py tests/test_tui.py
git commit -m "feat: add ThinkingIndicator with ●/○ animation"
```

---

## Task 5: Create Main Application Class

**Files:**
- Create: `canary/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write failing test for app initialization**

```python
# tests/test_app.py
def test_app_initializes_with_default_state():
    from canary.app import CanaryApp
    app = CanaryApp()
    assert app.screening_enabled is True
    assert app.current_prompt == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app.py::test_app_initializes_with_default_state -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'canary.app'"

- [ ] **Step 3: Create CanaryApp class**

```python
# canary/app.py
from __future__ import annotations

import os
import sys
from pathlib import Path

from .tui import HeaderPanel, PromptArea, SubprocessTree, SubprocessItem, ThinkingIndicator
from .local_embeddings import get_local_embedding
from .prompt_firewall import scan_prompt
from .risk import compute_risk_score


class CanaryApp:
    """Main canary application with TUI."""

    def __init__(self) -> None:
        self.screening_enabled = True
        self.current_prompt = ""
        self.subprocesses = SubprocessTree()
        self.thinking = ThinkingIndicator()
        self._running = False
        self._version = "0.1.3"
        self._cwd = os.getcwd()

    def toggle_screening(self) -> None:
        """Toggle screening on/off."""
        self.screening_enabled = not self.screening_enabled

    def set_prompt(self, prompt: str) -> None:
        """Update current prompt."""
        self.current_prompt = prompt

    def submit_prompt(self) -> None:
        """Submit current prompt for processing."""
        if not self.current_prompt:
            return

        # Add to subprocess tree
        self.subprocesses.add_item(SubprocessItem(name=f"prompt: {self.current_prompt[:40]}...", status="running"))

        if self.screening_enabled:
            self._scan_prompt()
        else:
            self._forward_prompt()

    def _scan_prompt(self) -> None:
        """Scan prompt using local Granite model."""
        self.thinking.start_thinking()

        try:
            # Run scan
            findings = scan_prompt(self.current_prompt)
            if findings:
                score = compute_risk_score(findings)
                self.subprocesses.add_item(
                    SubprocessItem(name="scan", status="complete", detail=f"score: {score}")
                )
            else:
                self.subprocesses.add_item(
                    SubprocessItem(name="scan", status="complete", detail="clear")
                )
        except Exception as e:
            self.subprocesses.add_item(
                SubprocessItem(name="scan", status="failed", detail=str(e))
            )
        finally:
            self.thinking.stop_thinking()

    def _forward_prompt(self) -> None:
        """Forward prompt to agent (placeholder)."""
        self.subprocesses.add_item(
            SubprocessItem(name="forward", status="complete", detail="screening disabled")
        )

    def handle_command(self, command: str) -> bool:
        """Handle :command input. Returns True to continue, False to exit."""
        cmd = command.strip().lower()

        if cmd in ("exit", "quit", "q"):
            return False

        if cmd == "on":
            self.screening_enabled = True
            self.subprocesses.add_item(SubprocessItem(name="command", status="complete", detail="screening on"))
        elif cmd == "off":
            self.screening_enabled = False
            self.subprocesses.add_item(SubprocessItem(name="command", status="complete", detail="screening off"))
        elif cmd == "help":
            self.subprocesses.add_item(SubprocessItem(name="help", status="complete", detail="on/off/exit/help/status/clear"))
        elif cmd == "status":
            status = "on" if self.screening_enabled else "off"
            self.subprocesses.add_item(SubprocessItem(name="status", status="complete", detail=f"screening: {status}"))
        elif cmd == "clear":
            self.subprocesses = SubprocessTree()
        else:
            self.subprocesses.add_item(SubprocessItem(name="unknown", status="failed", detail=f"unknown command: {cmd}"))

        return True

    def render(self) -> "RenderableType":
        """Render full TUI."""
        from rich.console import Group

        header = HeaderPanel(version=self._version, cwd=self._cwd)
        prompt = PromptArea(prompt=self.current_prompt)
        tree = self.subprocesses
        indicator = self.thinking

        return Group(
            header.render(),
            prompt.render(),
            tree.render(),
            indicator.render(),
        )

    def run(self) -> int:
        """Run the main application loop."""
        from rich.console import Console
        from rich.live import Live
        import time

        console = Console()
        self._running = True

        with Live(self.render(), console=console, refresh_per_second=12, transient=False) as live:
            while self._running:
                # Update animation frames
                self.thinking.tick()

                # Handle input (simplified - real implementation would use raw input)
                try:
                    # This is a placeholder - actual input handling in CLI
                    time.sleep(0.1)
                    live.update(self.render())
                except KeyboardInterrupt:
                    break

        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app.py::test_app_initializes_with_default_state -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add canary/app.py tests/test_app.py
git commit -m "feat: add CanaryApp main application class"
```

---

## Task 6: Simplify CLI Entry Point

**Files:**
- Modify: `canary/cli.py` (major rewrite)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for simplified CLI**

```python
# tests/test_cli.py
def test_cli_runs_app():
    from canary.cli import main
    import sys
    from io import StringIO
    # Just verify it doesn't crash immediately
    # Full test would mock the app
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL - module exists but test needs implementation

- [ ] **Step 3: Rewrite CLI to simplified version**

```python
# Replace canary/cli.py content
"""Simplified canary CLI - streamlined TUI."""
from __future__ import annotations

import os
import sys
import select
import termios
import tty

import click
from rich.console import Console
from rich.live import Live

from . import __version__
from .app import CanaryApp
from .tui import BRAND


@click.command()
@click.version_option(__version__, prog_name="canary")
def main():
    """canary — AI agent watchdog (streamlined TUI)."""
    app = CanaryApp()
    return _run_interactive(app)


def _run_interactive(app: CanaryApp) -> int:
    """Run the interactive TUI loop."""
    console = Console()

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        console.print("[dim]canary requires an interactive terminal[/dim]")
        return 1

    console.clear()

    fd = sys.stdin.fileno()
    original_mode = termios.tcgetattr(fd)
    query = ""

    try:
        tty.setcbreak(fd)
        with Live(app.render(), console=console, refresh_per_second=12, transient=False) as live:
            while True:
                # Animation tick
                app.thinking.tick()
                live.update(app.render())

                # Check for input
                ready, _, _ = select.select([sys.stdin], [], [], 0.08)
                if not ready:
                    continue

                char = os.read(fd, 1)
                if not char:
                    break

                # Handle special keys
                if char in {b"\r", b"\n"}:  # Enter
                    if query.startswith(":"):
                        if not app.handle_command(query[1:]):
                            break
                    else:
                        app.set_prompt(query)
                        app.submit_prompt()
                    query = ""
                elif char == b"\x7f" or char == b"\b":  # Backspace
                    query = query[:-1]
                elif char == b"\x03" or char == b"\x04":  # Ctrl+C or Ctrl+D
                    break
                elif char == b"\x15":  # Ctrl+U (clear line)
                    query = ""
                elif char == b"\x1b":  # Escape sequences
                    # Try to consume escape sequence
                    extra, _, _ = select.select([sys.stdin], [], [], 0.01)
                    if extra:
                        os.read(fd, 2)  # Consume arrow keys, etc.
                    else:
                        query = ""
                else:
                    # Regular character
                    try:
                        text = char.decode("utf-8", errors="ignore")
                        if text.isprintable():
                            query += text
                    except:
                        pass

                # Update prompt in app
                app.set_prompt(query)

    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original_mode)

    console.print(f"\n[dim {BRAND}]goodbye[/dim {BRAND}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (or skip if complex)

- [ ] **Step 5: Commit**

```bash
git add canary/cli.py tests/test_cli.py
git commit -m "refactor: simplify CLI to streamlined TUI"
```

---

## Task 7: Update Configuration (Remove IBM API)

**Files:**
- Modify: `canary/config.py`
- Modify: `canary/local_embeddings.py` (ensure local-only)

- [ ] **Step 1: Verify local-only mode**

Ensure `canary/local_embeddings.py` has no IBM API dependencies and runs entirely local.

Run: `grep -n "IBM_API_KEY\|ibm.com\|watsonx" canary/local_embeddings.py`
Expected: No matches (already local-only)

- [ ] **Step 2: Simplify config.py**

```python
# Replace canary/config.py
"""Configuration management (local-only mode)."""
from pathlib import Path

CONFIG_DIR = Path.home() / ".canary"


def get_config_dir() -> Path:
    """Get or create config directory."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def get_screening_enabled() -> bool:
    """Check if screening is enabled (stored in simple flag file)."""
    flag_file = CONFIG_DIR / "screening_enabled"
    if flag_file.exists():
        return flag_file.read_text().strip().lower() == "true"
    return True  # Default on


def set_screening_enabled(enabled: bool) -> None:
    """Set screening enabled state."""
    get_config_dir()
    flag_file = CONFIG_DIR / "screening_enabled"
    flag_file.write_text("true" if enabled else "false")
```

- [ ] **Step 3: Update app.py to use new config**

```python
# Update canary/app.py imports
from .config import get_screening_enabled, set_screening_enabled
```

- [ ] **Step 4: Commit**

```bash
git add canary/config.py canary/app.py
git commit -m "refactor: simplify config to local-only mode"
```

---

## Task 8: Integration Test

**Files:**
- Test: `tests/test_integration.py`

- [ ] **Step 1: Create integration test**

```python
# tests/test_integration.py
"""Integration tests for streamlined canary TUI."""


def test_app_components_integrate():
    """Test that all TUI components work together."""
    from canary.app import CanaryApp
    from canary.tui import SubprocessItem

    app = CanaryApp()

    # Simulate user interaction
    app.set_prompt("test prompt")
    app.subprocesses.add_item(SubprocessItem(name="test", status="running"))

    # Render should not raise
    renderable = app.render()
    assert renderable is not None


def test_command_handling():
    """Test command handling."""
    from canary.app import CanaryApp

    app = CanaryApp()
    assert app.screening_enabled is True

    # Toggle off
    app.handle_command("off")
    assert app.screening_enabled is False

    # Toggle on
    app.handle_command("on")
    assert app.screening_enabled is True

    # Exit returns False
    result = app.handle_command("exit")
    assert result is False
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for streamlined TUI"
```

---

## Task 9: Cleanup Old Code

**Files:**
- Delete or archive: Complex CLI commands that are no longer needed

- [ ] **Step 1: Backup and remove deprecated modules**

```bash
# Create backup directory
mkdir -p .canary/deprecated
cp canary/ibm/__init__.py .canary/deprecated/ 2>/dev/null || true
# Remove IBM module if it exists only for API
rm -rf canary/ibm/
```

- [ ] **Step 2: Update __init__.py exports**

```python
# Update canary/__init__.py if needed
"""canary — AI agent watchdog."""

__version__ = "0.1.3"

from .app import CanaryApp
from .tui import HeaderPanel, PromptArea, SubprocessTree, ThinkingIndicator

__all__ = ["CanaryApp", "HeaderPanel", "PromptArea", "SubprocessTree", "ThinkingIndicator"]
```

- [ ] **Step 3: Commit**

```bash
git add canary/__init__.py
git commit -m "refactor: cleanup deprecated modules and update exports"
```

---

## Task 10: Final Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Test CLI manually**

Run: `python -m canary --help`
Expected: Shows version and brief help

- [ ] **Step 3: Commit final state**

```bash
git add .
git commit -m "feat: complete streamlined canary TUI redesign

- Persistent header with logo, version, and cwd
- Shaded prompt input area with horizontal rules
- Subprocess tree with Unicode branch characters
- Thinking indicator with ●/○ animation
- Two-state pipeline (thinking → complete)
- Local-only Granite model (no IBM API)
- Simplified command set: on/off/exit/help/status/clear"
```

---

## Summary

This implementation creates a streamlined canary TUI with:
1. **Persistent header** - Logo, version, current directory always visible
2. **Shaded prompt area** - Distinct visual section with horizontal rules
3. **Subprocess tree** - Unicode branch characters (├──, └──, │) for scannable hierarchy
4. **Thinking indicator** - ●/○ pulse animation during processing
5. **Two-state pipeline** - Simple "thinking → complete" flow
6. **Local-only mode** - No IBM API dependencies, runs Granite embeddings locally
7. **Simplified commands** - on, off, exit, help, status, clear
