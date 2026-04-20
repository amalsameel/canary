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
