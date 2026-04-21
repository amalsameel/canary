"""Frontend state and command catalog for the terminal shell.

This keeps the shell closer to an app-style architecture: one source of truth
for command metadata, search behavior, and header-tip layout. The renderer in
`ui.py` and the input loop in `cli.py` both read from this catalog instead of
hardcoding separate command lists.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}


def _normalize_query(query: str) -> str:
    return query.removeprefix("/").strip().lower()


def _query_tokens(query: str) -> list[str]:
    parts = query.split()
    return [
        token
        for token in parts
        if token and token not in _STOPWORDS and (len(token) > 2 or len(parts) == 1)
    ]


def _subsequence_gap(needle: str, haystack: str) -> int | None:
    """Return a simple gap score when `needle` appears in order inside `haystack`."""
    if len(needle) < 2:
        return None

    previous = -1
    gap = 0
    for char in needle:
        cursor = haystack.find(char, previous + 1)
        if cursor < 0:
            return None
        if previous >= 0:
            gap += cursor - previous - 1
        previous = cursor
    return gap


@dataclass(frozen=True)
class ShellCommand:
    name: str
    summary: str
    keywords: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    def as_tuple(self) -> tuple[str, str]:
        return self.name, self.summary

    def matches_slash_prefix(self, query: str) -> bool:
        normalized = _normalize_query(query)
        if not normalized:
            return True
        return self.name[1:].startswith(normalized)

    def matches_query(self, query: str) -> bool:
        normalized = _normalize_query(query)
        if not normalized:
            return True
        tokens = _query_tokens(normalized)
        haystack = " ".join((self.name, self.summary, *self.keywords, *self.aliases)).lower()
        return normalized in haystack or any(token in haystack for token in tokens)

    def search_match(self, query: str) -> "CommandMatch | None":
        normalized = _normalize_query(query)
        if not normalized:
            return CommandMatch(command=self, source="command", matched_text="", priority=(99, 0))

        command_name = self.name.removeprefix("/").lower()
        aliases = tuple(alias.lower() for alias in self.aliases)
        keywords = tuple(keyword.lower() for keyword in self.keywords)
        summary = self.summary.lower()
        summary_words = tuple(summary.replace("/", " ").replace("-", " ").split())
        token_words = [
            command_name,
            *aliases,
            *keywords,
            *summary_words,
        ]
        tokens = _query_tokens(normalized)

        if normalized == command_name:
            return CommandMatch(self, source="command", matched_text=command_name, priority=(0, len(command_name)))

        for alias in aliases:
            if normalized == alias:
                return CommandMatch(self, source="alias", matched_text=alias, priority=(1, len(alias)))

        if command_name.startswith(normalized):
            return CommandMatch(self, source="command", matched_text=command_name, priority=(2, len(command_name)))

        for alias in aliases:
            if alias.startswith(normalized):
                return CommandMatch(self, source="alias", matched_text=alias, priority=(3, len(alias)))

        for keyword in keywords:
            if keyword.startswith(normalized):
                return CommandMatch(self, source="keyword", matched_text=keyword, priority=(4, len(keyword)))

        if tokens and all(any(word.startswith(token) for word in token_words) for token in tokens):
            best = normalized if len(tokens) > 1 else min(
                (word for word in token_words if any(word.startswith(token) for token in tokens)),
                key=len,
            )
            source = "summary" if best in summary_words or best == summary else "keyword"
            if best == command_name:
                source = "command"
            elif best in aliases:
                source = "alias"
            return CommandMatch(self, source=source, matched_text=best, priority=(5, len(best)))

        if normalized in command_name:
            return CommandMatch(self, source="command", matched_text=command_name, priority=(6, len(command_name)))

        for alias in aliases:
            if normalized in alias:
                return CommandMatch(self, source="alias", matched_text=alias, priority=(7, len(alias)))

        for keyword in keywords:
            if normalized in keyword:
                return CommandMatch(self, source="keyword", matched_text=keyword, priority=(8, len(keyword)))

        if normalized in summary:
            return CommandMatch(self, source="summary", matched_text=normalized, priority=(9, len(summary)))

        name_gap = _subsequence_gap(normalized, command_name)
        if name_gap is not None:
            return CommandMatch(self, source="fuzzy", matched_text=command_name, priority=(10, name_gap))

        fuzzy_candidates = [
            (candidate, _subsequence_gap(normalized, candidate))
            for candidate in (*aliases, *keywords)
        ]
        fuzzy_candidates = [
            (candidate, gap)
            for candidate, gap in fuzzy_candidates
            if gap is not None
        ]
        if fuzzy_candidates:
            candidate, gap = min(fuzzy_candidates, key=lambda item: (item[1], len(item[0])))
            source = "alias" if candidate in aliases else "keyword"
            return CommandMatch(self, source=source, matched_text=candidate, priority=(11, gap))

        return None


@dataclass(frozen=True)
class CommandMatch:
    command: ShellCommand
    source: str
    matched_text: str
    priority: tuple[int, ...]

    def as_tuple(self) -> tuple[str, str]:
        return self.command.as_tuple()

    @property
    def detail(self) -> str:
        if not self.matched_text or self.source == "command":
            return self.command.summary

        labels = {
            "alias": "alias",
            "keyword": "match",
            "summary": "about",
            "fuzzy": "fuzzy",
        }
        label = labels.get(self.source, "match")
        return f"{self.command.summary} · {label}: {self.matched_text}"


@dataclass(frozen=True)
class FrontendCatalog:
    commands: tuple[ShellCommand, ...]

    def rows(self) -> list[tuple[str, str]]:
        return [command.as_tuple() for command in self.commands]

    def slash_matches(self, buffer: str, *, limit: int) -> list[tuple[str, str]]:
        return [
            command.as_tuple()
            for command in self.commands
            if command.matches_slash_prefix(buffer)
        ][:limit]

    def search_matches(self, buffer: str, *, limit: int) -> list[CommandMatch]:
        normalized = _normalize_query(buffer)
        if not normalized:
            return [
                CommandMatch(command=command, source="command", matched_text="", priority=(99, idx))
                for idx, command in enumerate(self.commands[:limit])
            ]

        matches: list[CommandMatch] = []
        for idx, command in enumerate(self.commands):
            match = command.search_match(buffer)
            if match is None:
                continue
            matches.append(
                CommandMatch(
                    command=match.command,
                    source=match.source,
                    matched_text=match.matched_text,
                    priority=(*match.priority, idx),
                )
            )

        matches.sort(key=lambda match: match.priority)
        return matches[:limit]

    def search(self, buffer: str, *, limit: int) -> list[tuple[str, str]]:
        return [match.as_tuple() for match in self.search_matches(buffer, limit=limit)]

    def tip_columns(self, columns: int = 2) -> list[list[ShellCommand]]:
        if columns <= 1:
            return [list(self.commands)]

        size = (len(self.commands) + columns - 1) // columns
        return [list(self.commands[idx: idx + size]) for idx in range(0, len(self.commands), size)]


def prompt_segments(buffer: str) -> list[tuple[str, bool]]:
    """Split prompt text into (segment, is_command_highlight) pieces.

    If the prompt starts with `/`, only the leading slash command token is
    highlighted. Everything after the first whitespace is plain prompt text.
    """
    if not buffer:
        return []
    if not buffer.startswith("/"):
        return [(buffer, False)]

    for idx, char in enumerate(buffer):
        if char.isspace():
            return [(buffer[:idx], True), (buffer[idx:], False)]
    return [(buffer, True)]


@dataclass
class ShellSessionState:
    launch_target_name: str | None = None
    launch_target_path: str | None = None
    audit_active: bool = False
    audit_started_at: float | None = None
    audit_tmux_pane: str | None = None
    audit_external: bool = False  # True when audit is running in external terminal
    watch_active: bool = False
    watch_target: str | None = None
    watch_idle_seconds: int | None = None
    watch_continuous: bool = False

    @property
    def launch_label(self) -> str:
        return self.launch_target_name or "no launch target"

    def set_launch_target(self, name: str, path: str) -> None:
        self.launch_target_name = name
        self.launch_target_path = path

    def clear_launch_target(self) -> None:
        self.launch_target_name = None
        self.launch_target_path = None

    def set_audit(self, enabled: bool, *, external: bool = False) -> None:
        self.audit_active = enabled
        self.audit_external = enabled and external
        self.audit_started_at = time.time() if enabled else None
        if not enabled:
            self.audit_tmux_pane = None
            self.audit_external = False

    def set_audit_tmux_pane(self, pane_id: str | None) -> None:
        self.audit_tmux_pane = pane_id if self.audit_active else None

    def set_watch(
        self,
        enabled: bool,
        target: str | None = None,
        *,
        idle_seconds: int | None = None,
        continuous: bool = False,
    ) -> None:
        self.watch_active = enabled
        self.watch_target = target if enabled else None
        self.watch_idle_seconds = idle_seconds if enabled else None
        self.watch_continuous = continuous if enabled else False


FRONTEND_CATALOG = FrontendCatalog(commands=(
    ShellCommand("/agent", "set coding agent", ("claude", "codex", "launch target", "switch agent", "select agent", "choose agent")),
    ShellCommand("/help", "command list", ("commands", "shortcuts", "manual"), aliases=("?",)),
    ShellCommand("/status", "shell state", ("screening", "watch", "launch", "health", "state")),
    ShellCommand("/on", "screening on", ("enable", "prompt", "allow")),
    ShellCommand("/off", "screening off", ("disable", "prompt", "pause")),
    ShellCommand("/audit", "live risk window", ("bash", "terminal", "monitor", "risk", "feed")),
    ShellCommand("/perms", "always allowed bash commands", ("permissions", "allowlist", "allowed", "bash", "settings", "claude")),
    ShellCommand("/watch", "repo drift watch", ("files", "surveillance", "changes", "repo", "repository", "monitor")),
    ShellCommand("/checkpoint", "save restore point", ("snapshot", "save", "checkpoint"), aliases=("snap",)),
    ShellCommand("/rollback", "restore point", ("undo", "restore", "revert")),
    ShellCommand("/log", "recent events", ("history", "session", "timeline")),
    ShellCommand("/checkpoints", "restore points", ("snapshots", "list", "history")),
    ShellCommand("/docs", "open docs topics", ("guide", "manual", "readme", "help topics")),
    ShellCommand("/setup", "refresh local setup", ("install", "bootstrap", "dependencies")),
    ShellCommand("/guard", "manage launch shims", ("hooks", "protect", "shield", "shims")),
    ShellCommand("/clear", "clear activity", ("reset", "history", "wipe")),
    ShellCommand("/exit", "close canary", ("quit", "leave"), aliases=("q", "quit")),
))
