import io
import os
import re
import time
from types import SimpleNamespace

import pytest
from rich.console import Console

from canary.cli import SHELL_COMMANDS, _ANSI_SEARCH_BG, _AuditShellBody, _PinnedShellBlock, _PromptBufferState, _PromptInputParser, _ShellSubprocessView, _apply_prompt_escape_sequence, _audit_dashboard_renderable, _collect_watch_prompt, _confirm_risky_shell_handoff, _discover_active_transcripts, _editor_suggestion_lines, _handle_shell_command, _launch_agent_terminal, _launch_audit_terminal, _launch_watch_session, _run_selected_agent, _searchable_entries, _shell_home_renderable, _slash_command_matches, _update_choice_selection
from canary.frontend import ShellSessionState
from canary.ui import ACCENT, SEARCH_SURFACE, SURFACE, SubprocessLog, WHITE, prompt_choice_bar, _glimmer_indices


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_slash_command_matches_returns_defaults_for_empty_query():
    matches = _slash_command_matches("/")

    assert matches
    assert matches[0][0] == "/agent"


def test_slash_command_matches_filters_by_prefix():
    matches = _slash_command_matches("/au")

    assert ("/audit", "live risk window") in matches
    assert all(name.startswith("/a") for name, _ in matches)


def test_slash_command_matches_does_not_include_substring_matches():
    matches = _slash_command_matches("/it")

    assert matches == []


def test_searchable_entries_show_full_catalog_and_filter_normally():
    assert _searchable_entries("") == SHELL_COMMANDS
    assert ("/watch", "repo drift watch") in _searchable_entries("watch the repo")
    assert all(name != "/usage" for name, _ in _searchable_entries(""))
    assert ("/agent", "set coding agent") in _searchable_entries("")
    assert ("/docs", "open docs topics") in _searchable_entries("")
    assert ("/perms", "always allowed bash commands") in _searchable_entries("")
    assert ("/setup", "refresh local setup") in _searchable_entries("")
    assert ("/guard", "manage launch shims") in _searchable_entries("")
    assert _searchable_entries("/") == _slash_command_matches("/", limit=len(SHELL_COMMANDS))
    assert _searchable_entries("/codex")[0] == ("/agent", "set coding agent")
    assert _searchable_entries("/q")[0] == ("/exit", "close canary")


def test_editor_suggestion_lines_hide_source_badges_and_use_search_surface():
    lines = _editor_suggestion_lines("/codex", width=80)

    assert lines
    rendered = "\n".join(lines)
    assert "MATCH" not in rendered
    assert "ABOUT" not in rendered
    assert _ANSI_SEARCH_BG in rendered


def test_search_surface_is_lighter_than_base_terminal_surface():
    base = int(SURFACE.lstrip("#"), 16)
    search = int(SEARCH_SURFACE.lstrip("#"), 16)

    assert search > base


def test_shell_home_renderable_keeps_prompt_and_suggestions_in_one_scene():
    renderable = _shell_home_renderable(
        ["09:00  ·  screening enabled"],
        launch_target="codex",
        prompt="/codex",
        show_prompt_lane=True,
    )
    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=120)

    render_console.print(renderable)
    text = _strip_ansi(output.getvalue())

    assert "canary" in text.lower()
    assert "███████" in text
    assert "/agent" in text


def test_shell_home_renderable_removes_plain_text_screens_header_copy():
    renderable = _shell_home_renderable(
        ["09:00  ·  screening enabled"],
        launch_target="codex",
        prompt="/agent",
        show_prompt_lane=True,
    )
    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=120)

    render_console.print(renderable)
    text = _strip_ansi(output.getvalue())

    assert "plain text screens before handoff" not in text


def test_shell_home_renderable_places_latest_submission_above_status_and_input():
    renderable = _shell_home_renderable(
        ["09:00  ·  screening enabled"],
        launch_target="codex",
        prompt="/agent claude",
        submitted_prompt="fix login flow",
        submitted_prompt_state="running",
        status="status block",
        show_prompt_lane=True,
    )
    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=120)

    render_console.print(renderable)
    text = _strip_ansi(output.getvalue())

    assert text.index("fix login flow") < text.index("status block") < text.rindex("/agent claude")


def test_pinned_shell_block_updates_in_place():
    stream = io.StringIO()
    block = _PinnedShellBlock(stream=stream, width=80, color_system="truecolor")
    renders = [["header", "prompt"], ["header", "prompt updated"]]
    block._render_lines = lambda renderable: renders.pop(0)  # type: ignore[method-assign]

    block.mount(object())
    block.update(object())
    block.close()
    output = stream.getvalue()

    assert output.startswith("\x1b[?1049h")
    assert output.count("\x1b[H\x1b[2J") == 2
    assert output.count("\x1b[2K") == 4
    assert output.endswith("\x1b[?1049l")


def test_prompt_buffer_state_inserts_at_cursor():
    state = _PromptBufferState()

    assert state.insert_text("abcd") is True
    assert state.move_left() is True
    assert state.move_left() is True
    assert state.insert_text("XY") is True

    assert state.text == "abXYcd"
    assert state.cursor_pos == 4


def test_prompt_buffer_state_summarizes_large_paste():
    state = _PromptBufferState()

    assert state.insert_text("word " * 150, source="paste") is True

    assert state.show_paste_summary is True
    assert state.paste_word_count == 150
    assert state.paste_line_count == 1


def test_prompt_escape_sequence_supports_navigation_and_delete():
    state = _PromptBufferState(list("abcd"), cursor_pos=4)

    assert _apply_prompt_escape_sequence(state, "[D") is True
    assert state.cursor_pos == 3
    assert _apply_prompt_escape_sequence(state, "[H") is True
    assert state.cursor_pos == 0
    assert _apply_prompt_escape_sequence(state, "[3~") is True

    assert state.text == "bcd"
    assert state.cursor_pos == 0


def test_prompt_input_parser_handles_batched_text():
    parser = _PromptInputParser()

    assert parser.feed("ab") == [("text", "a"), ("text", "b")]


def test_prompt_input_parser_decodes_navigation_sequence_across_chunks():
    parser = _PromptInputParser()

    assert parser.feed("\x1b") == []
    assert parser.feed("[D") == [("escape", "[D")]


def test_prompt_input_parser_decodes_vertical_navigation_sequence_across_chunks():
    parser = _PromptInputParser()

    assert parser.feed("\x1b") == []
    assert parser.feed("[A") == [("escape", "[A")]


def test_prompt_input_parser_collects_bracketed_paste_across_chunks():
    parser = _PromptInputParser()

    assert parser.feed("\x1b[200~fix") == []
    assert parser.feed("\nlogin") == []
    assert parser.feed("\x1b[201~") == [("paste", "fix\nlogin")]


def test_update_choice_selection_supports_arrow_keys_and_number_shortcuts():
    assert _update_choice_selection(1, 2, escape="[A") == 0
    assert _update_choice_selection(0, 2, escape="[C") == 1
    assert _update_choice_selection(0, 2, text="2") == 1
    assert _update_choice_selection(1, 2, text="1") == 0


def test_prompt_choice_bar_highlights_selected_option_in_green():
    renderable = prompt_choice_bar(
        "continue?",
        ["Yes", "No"],
        selected_index=0,
        hint="Click Enter when confirmed",
    )
    option_row = renderable.renderables[2]

    assert option_row.plain.strip().startswith("Yes")
    assert option_row.plain.strip().endswith("No")
    assert any(
        span.style == f"bold {ACCENT} on {SURFACE}"
        and option_row.plain[span.start:span.end] == "Yes"
        for span in option_row.spans
    )
    assert any(
        span.style == f"bold {WHITE} on {SURFACE}"
        and option_row.plain[span.start:span.end] == "No"
        for span in option_row.spans
    )

    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=80, color_system="truecolor")
    render_console.print(renderable)
    text = output.getvalue()

    assert "continue?" in _strip_ansi(text)
    assert "Yes" in _strip_ansi(text)
    assert "No" in _strip_ansi(text)


def test_confirm_risky_shell_handoff_allows_confirmed_prompt(monkeypatch):
    state = ShellSessionState(launch_target_name="codex", launch_target_path="/tmp/codex")
    prompt_log = SubprocessLog(animated=False)
    prompt_log.add("prompt", "submitted 'fix auth'", "complete")
    prompt_log.add("shield", "prompt cleared", "complete")
    prompt_log.add("semantic scan", "anchors compared", "complete")
    prompt_log.add("launch target", "waiting to hand off into codex", "pending")
    finding = SimpleNamespace(severity="HIGH", description="Credential handling")
    refreshed = []

    monkeypatch.setattr("canary.cli._confirm", lambda prompt, default="n": True)

    allowed, renderable = _confirm_risky_shell_handoff(
        [finding],
        prompt_log=prompt_log,
        agent_name="codex",
        session_state=state,
        refresh_shell=lambda view: refreshed.append(view),
    )

    assert allowed is True
    assert refreshed
    assert renderable is not None
    assert any(name == "shield" and detail == "risky prompt approved" and status == "complete" for name, detail, status, _ in prompt_log.items)
    assert any(name == "launch target" and "user confirmed risky handoff into codex" in detail and status == "pending" for name, detail, status, _ in prompt_log.items)


def test_confirm_risky_shell_handoff_blocks_declined_prompt(monkeypatch):
    state = ShellSessionState(launch_target_name="codex", launch_target_path="/tmp/codex")
    prompt_log = SubprocessLog(animated=False)
    prompt_log.add("prompt", "submitted 'fix auth'", "complete")
    prompt_log.add("shield", "prompt cleared", "complete")
    prompt_log.add("semantic scan", "anchors compared", "complete")
    prompt_log.add("launch target", "waiting to hand off into codex", "pending")
    finding = SimpleNamespace(severity="HIGH", description="Credential handling")

    monkeypatch.setattr("canary.cli._confirm", lambda prompt, default="n": False)

    allowed, renderable = _confirm_risky_shell_handoff(
        [finding],
        prompt_log=prompt_log,
        agent_name="codex",
        session_state=state,
        refresh_shell=lambda _: None,
    )

    assert allowed is False
    assert renderable is not None
    assert any(name == "shield" and detail == "blocked risky prompt" and status == "complete" for name, detail, status, _ in prompt_log.items)
    assert any(name == "launch target" and detail == "blocked - risky content detected" and status == "failed" for name, detail, status, _ in prompt_log.items)

    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=160)
    render_console.print(renderable)
    text = _strip_ansi(output.getvalue())

    assert "Prompt blocked" in text
    assert "Canary kept the risky prompt from reaching the agent." in text


def test_collect_watch_prompt_accepts_risky_preset_when_confirmed(monkeypatch):
    finding = SimpleNamespace(severity="HIGH", description="Credential handling")

    monkeypatch.setattr("canary.cli._review_prompt", lambda *args, **kwargs: ([finding], 80))
    monkeypatch.setattr("canary.cli._confirm", lambda prompt, default="n": True)

    assert _collect_watch_prompt(".", "fix auth", agent_name="codex") == "fix auth"


def test_collect_watch_prompt_blocks_risky_preset_when_declined(monkeypatch):
    finding = SimpleNamespace(severity="HIGH", description="Credential handling")
    failures = []

    monkeypatch.setattr("canary.cli._review_prompt", lambda *args, **kwargs: ([finding], 80))
    monkeypatch.setattr("canary.cli._confirm", lambda prompt, default="n": False)
    monkeypatch.setattr("canary.cli.fail", lambda text, detail=None: failures.append((text, detail)))
    monkeypatch.setattr("canary.cli.console.print", lambda *args, **kwargs: None)

    assert _collect_watch_prompt(".", "fix auth", agent_name="codex") is None
    assert failures == [("blocked", "edit the prompt or enter y to hand it off anyway")]


def test_launch_audit_terminal_is_disabled_when_env_off(monkeypatch):
    calls = []

    monkeypatch.setenv("CANARY_ALLOW_PARALLEL_TERMINALS", "0")
    monkeypatch.setattr("canary.cli.sys.platform", "darwin", raising=False)
    monkeypatch.setattr("canary.cli.subprocess.run", lambda *args, **kwargs: calls.append(args[0]) or SimpleNamespace(returncode=0))

    assert _launch_audit_terminal() is False
    assert calls == []


def test_launch_audit_terminal_can_still_open_when_opted_in(monkeypatch):
    calls = []

    monkeypatch.setenv("CANARY_ALLOW_PARALLEL_TERMINALS", "1")
    monkeypatch.setattr("canary.cli.sys.platform", "darwin", raising=False)
    monkeypatch.setattr("canary.cli.subprocess.run", lambda *args, **kwargs: calls.append(args[0]) or SimpleNamespace(returncode=0))

    assert _launch_audit_terminal() is True
    assert calls
    assert "--dashboard" in calls[0][2]
    assert "--idle" not in calls[0][2]
    assert not any("activate" in part for part in calls[0])


def test_launch_audit_terminal_can_track_parent_and_close_tab(monkeypatch):
    calls = []

    monkeypatch.setenv("CANARY_ALLOW_PARALLEL_TERMINALS", "1")
    monkeypatch.setattr("canary.cli.sys.platform", "darwin", raising=False)
    monkeypatch.setattr("canary.cli.subprocess.run", lambda *args, **kwargs: calls.append(args[0]) or SimpleNamespace(returncode=0))

    assert _launch_audit_terminal(parent_pid=4321, close_tab_on_exit=True) is True
    assert calls
    assert "--parent-pid 4321" in calls[0][2]
    assert "; exit" in calls[0][2]


def test_launch_agent_terminal_opens_new_terminal_in_target_directory(monkeypatch):
    calls = []

    monkeypatch.setenv("CANARY_ALLOW_PARALLEL_TERMINALS", "1")
    monkeypatch.setattr("canary.cli.sys.platform", "darwin", raising=False)
    monkeypatch.setattr("canary.cli.subprocess.run", lambda *args, **kwargs: calls.append(args[0]) or SimpleNamespace(returncode=0))

    assert _launch_agent_terminal(["/tmp/codex", "fix login flow"], cwd="/tmp/project") is True
    assert calls
    assert "cd /tmp/project;" in calls[0][2]
    assert "/tmp/codex 'fix login flow'" in calls[0][2]


def test_run_selected_agent_runs_inline_by_default(monkeypatch):
    runs = []
    restored = []
    recent_activity = []

    monkeypatch.setattr("canary.cli._restore_terminal_cursor", lambda: restored.append(True))
    monkeypatch.setattr("canary.cli.subprocess.run", lambda *args, **kwargs: runs.append((args[0], kwargs.get("cwd"))) or SimpleNamespace(returncode=0))

    _run_selected_agent("/tmp/codex", "fix login flow", agent_name="codex", recent_activity=recent_activity)

    assert runs == [(["/tmp/codex", "fix login flow"], os.getcwd())]
    assert restored == [True]
    assert "session returned" in recent_activity[-1]


def test_run_selected_agent_uses_ephemeral_tmux_session_for_live_audit(monkeypatch):
    recent_activity = []
    state = ShellSessionState(
        launch_target_name="codex",
        launch_target_path="/tmp/codex",
        audit_active=True,
    )
    restored = []

    monkeypatch.setattr("canary.cli._tmux_available", lambda: True)
    monkeypatch.setattr("canary.cli._tmux_in_session", lambda: False)
    monkeypatch.setattr("canary.cli._run_agent_in_ephemeral_tmux_session", lambda argv, cwd: 0)
    monkeypatch.setattr("canary.cli._restore_terminal_cursor", lambda: restored.append(True))
    monkeypatch.setattr("canary.cli.subprocess.run", lambda *args, **kwargs: pytest.fail("subprocess.run should not be used when tmux session handoff succeeds"))

    _run_selected_agent(
        "/tmp/codex",
        "fix login flow",
        agent_name="codex",
        recent_activity=recent_activity,
        session_state=state,
    )

    assert restored == [True]
    assert "session returned" in recent_activity[-1]


def test_watch_session_runs_inline_in_current_terminal(monkeypatch):
    runs = []

    monkeypatch.setattr("canary.cli._resolve_watch_agent", lambda: ("codex", "/tmp/codex"))
    monkeypatch.setattr("canary.cli._collect_watch_prompt", lambda target, prompt, agent_name, **kwargs: "fix login flow")
    monkeypatch.setattr("canary.cli._watch_already_running", lambda: None)
    monkeypatch.setattr("canary.cli._spawn_background_watch", lambda target, idle, continuous: SimpleNamespace(pid=999))
    monkeypatch.setattr("canary.cli.animate_pipeline", lambda *args, **kwargs: None)
    monkeypatch.setattr("canary.cli.subprocess.run", lambda *args, **kwargs: runs.append((args[0], kwargs.get("cwd"))) or SimpleNamespace(returncode=0))

    with pytest.raises(SystemExit) as exc:
        _launch_watch_session(".", idle=30, continuous=False, prompt="fix login flow", check_only=False)

    assert exc.value.code == 0
    assert runs == [(["/tmp/codex", "fix login flow"], os.path.abspath("."))]


def test_audit_glimmer_moves_three_characters_through_word_and_ellipsis():
    label = "Auditing..."
    expected = [
        "A",
        "Au",
        "Aud",
        "udi",
        "dit",
        "iti",
        "tin",
        "ing",
        "ng.",
        "g..",
        "...",
        "..",
        ".",
    ]

    actual = []
    for frame in range(len(expected)):
        active = "".join(label[idx] for idx in sorted(_glimmer_indices(label, frame)))
        actual.append(active)

    assert actual == expected


def test_audit_dashboard_is_persistent_until_ctrl_c():
    renderable = _audit_dashboard_renderable({}, [], last_event_time=time.time())
    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=120)

    render_console.print(renderable)
    text = _strip_ansi(output.getvalue())

    assert "auditing..." in text
    assert "current requests" in text
    assert "past requests" in text
    assert "Ctrl-C to stop" in text
    assert "bash audit" not in text.lower()
    assert "idle timeout" not in text
    assert "live bash review" not in text


def test_status_command_shows_only_current_subprocesses(monkeypatch):
    recent_activity = []
    state = ShellSessionState(launch_target_name="codex", launch_target_path="/tmp/codex")
    command_log = SubprocessLog()
    monkeypatch.setattr("canary.cli.get_enabled", lambda: True)

    should_continue, renderable = _handle_shell_command(
        "/status",
        recent_activity,
        state,
        subprocess_log=command_log,
        refresh_status=lambda _: None,
    )

    assert should_continue is True
    assert renderable is not None

    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=160)
    render_console.print(renderable)
    text = _strip_ansi(output.getvalue())

    assert "shield" in text
    assert "launch target" in text
    assert "prompt firewall armed" in text
    assert "launch target set to codex" in text
    assert "audit" not in text.lower()
    assert "watch" not in text.lower()
    assert "repo drift watch armed" not in text


def test_shell_subprocess_view_renders_one_connected_tree(monkeypatch):
    state = ShellSessionState(launch_target_name="codex", launch_target_path="/tmp/codex")
    command_log = SubprocessLog(animated=False)
    command_log.add("/agent", "launch target set to codex", "complete")
    monkeypatch.setattr("canary.cli.get_enabled", lambda: True)

    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=160)
    render_console.print(_ShellSubprocessView(state, command_log=command_log))
    text = _strip_ansi(output.getvalue())

    assert "├─ ✓ /agent  done" in text
    assert "│   launch target set to codex" in text
    assert "├─ ✓ shield  done" in text
    assert "╰─ ✓ launch target  done" in text
    assert "\n\n├─ ✓ shield  done" not in text


def test_shell_subprocess_view_hides_inline_audit_body_when_tmux_pane_is_live(monkeypatch):
    state = ShellSessionState(
        launch_target_name="codex",
        launch_target_path="/tmp/codex",
        audit_active=True,
        audit_tmux_pane="%42",
    )
    monkeypatch.setattr("canary.cli.get_enabled", lambda: True)

    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=160)
    render_console.print(_ShellSubprocessView(state, body=_AuditShellBody()))
    text = _strip_ansi(output.getvalue())

    assert "current tmux terminal pane" in text
    assert "/audit exit" not in text


def test_watch_command_arms_watch_state_only_when_explicitly_called(monkeypatch):
    recent_activity = []
    state = ShellSessionState(launch_target_name="codex", launch_target_path="/tmp/codex")

    pauses = []
    monkeypatch.setattr("canary.cli._watch_already_running", lambda: None)
    monkeypatch.setattr("canary.cli._spawn_background_watch", lambda target, idle, continuous: SimpleNamespace(pid=999))
    monkeypatch.setattr("canary.cli._shell_pause", lambda prompt="press enter to return": pauses.append(prompt))

    should_continue, renderable = _handle_shell_command("/watch .", recent_activity, state)

    assert should_continue is True
    assert renderable is not None
    assert pauses == []
    assert state.watch_active is True
    assert state.watch_target == os.path.abspath(".")


def test_audit_command_stays_inline_without_pausing_shell(monkeypatch):
    pauses = []
    recent_activity = []
    state = ShellSessionState(launch_target_name="codex", launch_target_path="/tmp/codex")

    monkeypatch.setattr("canary.cli._shell_pause", lambda prompt="press enter to return": pauses.append(prompt))
    monkeypatch.setattr("canary.cli._audit_already_running", lambda: None)
    monkeypatch.setattr("canary.cli._spawn_background_audit", lambda **kwargs: SimpleNamespace(pid=999))

    should_continue, renderable = _handle_shell_command("/audit", recent_activity, state)

    assert should_continue is True
    assert renderable is not None
    assert pauses == []
    assert state.audit_active is True

    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=160)
    render_console.print(renderable)
    text = _strip_ansi(output.getvalue())

    assert "audit" in text.lower()
    assert "companion audit stream live" in text


def test_watch_command_reuses_existing_watch_without_already_running_copy(monkeypatch):
    recent_activity = []
    state = ShellSessionState(launch_target_name="codex", launch_target_path="/tmp/codex")

    monkeypatch.setattr("canary.cli._watch_already_running", lambda: 1234)

    should_continue, renderable = _handle_shell_command("/watch .", recent_activity, state)

    assert should_continue is True
    assert renderable is not None
    assert state.watch_active is True
    assert "already running" not in recent_activity[-1]


def test_audit_exit_clears_active_audit_state():
    recent_activity = []
    state = ShellSessionState(
        launch_target_name="codex",
        launch_target_path="/tmp/codex",
        audit_active=True,
    )

    should_continue, renderable = _handle_shell_command("/audit exit", recent_activity, state)

    assert should_continue is True
    assert renderable is not None
    assert state.audit_active is False


def test_audit_exit_closes_tmux_pane_when_present(monkeypatch):
    recent_activity = []
    state = ShellSessionState(
        launch_target_name="codex",
        launch_target_path="/tmp/codex",
        audit_active=True,
        audit_tmux_pane="%42",
    )
    closed = []

    monkeypatch.setattr("canary.cli._close_tmux_pane", lambda pane_id: closed.append(pane_id) or True)

    should_continue, renderable = _handle_shell_command("/audit exit", recent_activity, state)

    assert should_continue is True
    assert renderable is not None
    assert closed == ["%42"]
    assert state.audit_tmux_pane is None


def test_watch_exit_stops_active_watch(monkeypatch, tmp_path):
    recent_activity = []
    state = ShellSessionState(
        launch_target_name="codex",
        launch_target_path="/tmp/codex",
        watch_active=True,
        watch_target=os.path.abspath("."),
    )
    signals = []
    pid_path = tmp_path / "watch.pid"
    pid_path.write_text("4321")

    monkeypatch.setattr("canary.cli._watch_already_running", lambda: 4321)
    monkeypatch.setattr("canary.cli.os.kill", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr("canary.cli._WATCH_PID_PATH", pid_path)

    should_continue, renderable = _handle_shell_command("/watch exit", recent_activity, state)

    assert should_continue is True
    assert renderable is not None
    assert state.watch_active is False
    assert signals == [(4321, 15)]


def test_checkpoint_command_requires_name(tmp_path, monkeypatch):
    recent_activity = []
    state = ShellSessionState(launch_target_name="codex", launch_target_path="/tmp/codex")
    monkeypatch.chdir(tmp_path)

    should_continue, renderable = _handle_shell_command("/checkpoint", recent_activity, state)

    assert should_continue is True
    assert renderable is not None

    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=160)
    render_console.print(renderable)
    text = _strip_ansi(output.getvalue())

    assert "checkpoint name required" in text


def test_checkpoint_command_can_create_and_delete_named_checkpoint(tmp_path, monkeypatch):
    recent_activity = []
    state = ShellSessionState(launch_target_name="codex", launch_target_path="/tmp/codex")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "notes.txt").write_text("ready")

    should_continue, create_renderable = _handle_shell_command("/checkpoint release-ready", recent_activity, state)

    assert should_continue is True
    assert create_renderable is not None
    assert (tmp_path / ".canary" / "checkpoints" / "release-ready").exists()

    should_continue, delete_renderable = _handle_shell_command("/checkpoint release-ready delete", recent_activity, state)

    assert should_continue is True
    assert delete_renderable is not None
    assert not (tmp_path / ".canary" / "checkpoints" / "release-ready").exists()


def test_status_command_uses_lowercase_audit_and_watch_labels_when_active():
    recent_activity = []
    state = ShellSessionState(
        launch_target_name="codex",
        launch_target_path="/tmp/codex",
        audit_active=True,
        watch_active=True,
        watch_target=os.path.abspath("."),
    )
    command_log = SubprocessLog()

    should_continue, renderable = _handle_shell_command(
        "/status",
        recent_activity,
        state,
        subprocess_log=command_log,
        refresh_status=lambda _: None,
    )

    assert should_continue is True
    assert renderable is not None

    output = io.StringIO()
    render_console = Console(file=output, force_terminal=True, width=160)
    render_console.print(renderable)
    text = _strip_ansi(output.getvalue())

    assert "audit" in text
    assert "watch" in text
    assert "Audit" not in text
    assert "Watch" not in text


def test_discover_active_transcripts_includes_recent_codex_sessions(monkeypatch, tmp_path):
    claude_dir = tmp_path / ".claude" / "projects"
    codex_dir = tmp_path / ".codex" / "sessions"
    codex_file = codex_dir / "2026" / "04" / "21" / "rollout.jsonl"
    stale_claude = claude_dir / "stale.jsonl"

    codex_file.parent.mkdir(parents=True)
    codex_file.write_text("{\"type\":\"session_meta\"}\n")
    stale_claude.parent.mkdir(parents=True)
    stale_claude.write_text("{\"type\":\"assistant\"}\n")
    old = time.time() - 3600
    os.utime(stale_claude, (old, old))

    monkeypatch.setattr("canary.cli.CLAUDE_PROJECTS_DIR", claude_dir)
    monkeypatch.setattr("canary.cli.CODEX_SESSIONS_DIR", codex_dir)

    found = _discover_active_transcripts(max_age_secs=600)

    assert str(codex_file) in found
    assert str(stale_claude) not in found


def test_run_selected_agent_reports_non_zero_exit(monkeypatch):
    failures = []
    pauses = []
    recent_activity = []

    monkeypatch.setattr("canary.cli.subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=42))
    monkeypatch.setattr("canary.cli._restore_terminal_cursor", lambda: None)
    monkeypatch.setattr("canary.cli._shell_pause", lambda prompt="press enter to return": pauses.append(prompt))
    monkeypatch.setattr("canary.cli.fail", lambda text, detail=None: failures.append((text, detail)))
    monkeypatch.setattr("canary.cli.console.print", lambda *args, **kwargs: None)

    _run_selected_agent("/tmp/fake-agent", "fix auth", agent_name="claude", recent_activity=recent_activity)

    assert failures == [("claude exited with code 42", "see agent output above")]
    assert pauses == ["press enter to return"]
    assert recent_activity and "claude exited with code 42" in recent_activity[-1]
