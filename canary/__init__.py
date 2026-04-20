"""canary — AI agent watchdog."""

__version__ = "0.1.3"

from .app import CanaryApp
from .tui import HeaderPanel, PromptArea, SubprocessTree, ThinkingIndicator

__all__ = ["CanaryApp", "HeaderPanel", "PromptArea", "SubprocessTree", "ThinkingIndicator"]
