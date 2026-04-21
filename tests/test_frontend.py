from canary.frontend import FRONTEND_CATALOG, ShellSessionState, prompt_segments


def test_frontend_catalog_search_supports_plain_queries():
    assert ("/watch", "repo drift watch") in FRONTEND_CATALOG.search("watch the repo", limit=20)
    assert ("/agent", "set coding agent") in FRONTEND_CATALOG.search("choose agent", limit=20)
    assert FRONTEND_CATALOG.search("/codex", limit=20)[0] == ("/agent", "set coding agent")
    assert FRONTEND_CATALOG.search("/restore", limit=20)[0] == ("/rollback", "restore point")


def test_frontend_catalog_builds_two_columns_evenly():
    columns = FRONTEND_CATALOG.tip_columns(columns=2)

    assert len(columns) == 2
    assert abs(len(columns[0]) - len(columns[1])) <= 1
    assert columns[0][0].name == "/agent"


def test_prompt_segments_only_highlights_leading_slash_command():
    assert prompt_segments("/agent claude") == [("/agent", True), (" claude", False)]
    assert prompt_segments("fix auth flow") == [("fix auth flow", False)]


def test_shell_session_state_tracks_explicit_audit_and_watch_modes():
    state = ShellSessionState()

    assert state.audit_active is False
    assert state.watch_active is False
    assert state.watch_target is None

    state.set_audit(True)
    state.set_watch(True, "/tmp/repo")

    assert state.audit_active is True
    assert state.watch_active is True
    assert state.watch_target == "/tmp/repo"

    state.set_watch(False)

    assert state.watch_active is False
    assert state.watch_target is None
