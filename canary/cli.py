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
