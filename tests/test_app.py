import pytest


@pytest.fixture(autouse=True)
def _isolated_config_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CANARY_CONFIG_DIR", str(tmp_path / ".canary"))


def test_app_initializes_with_default_state():
    from canary.app import CanaryApp
    app = CanaryApp()
    assert app.screening_enabled is True
    assert app.current_prompt == ""


def test_app_toggle_screening():
    from canary.app import CanaryApp
    app = CanaryApp()
    assert app.screening_enabled is True

    app.toggle_screening()
    assert app.screening_enabled is False

    app.toggle_screening()
    assert app.screening_enabled is True


def test_app_set_prompt():
    from canary.app import CanaryApp
    app = CanaryApp()
    assert app.current_prompt == ""

    app.set_prompt("test prompt")
    assert app.current_prompt == "test prompt"


def test_app_handle_command_exit():
    from canary.app import CanaryApp
    app = CanaryApp()

    # exit should return False
    result = app.handle_command("exit")
    assert result is False

    result = app.handle_command("quit")
    assert result is False

    result = app.handle_command("q")
    assert result is False


def test_app_handle_command_on_off():
    from canary.app import CanaryApp
    app = CanaryApp()

    # Turn off
    result = app.handle_command("off")
    assert result is True
    assert app.screening_enabled is False
    assert app.subprocesses.items[-1].detail == "screening off"

    # Turn on
    result = app.handle_command("on")
    assert result is True
    assert app.screening_enabled is True
    assert app.subprocesses.items[-1].detail == "screening on"


def test_app_handle_command_status():
    from canary.app import CanaryApp
    app = CanaryApp()

    result = app.handle_command("status")
    assert result is True
    assert app.subprocesses.items[-1].detail == "screening: on"

    app.toggle_screening()
    result = app.handle_command("status")
    assert app.subprocesses.items[-1].detail == "screening: off"


def test_app_handle_command_help():
    from canary.app import CanaryApp
    app = CanaryApp()

    result = app.handle_command("help")
    assert result is True
    assert "on/off/exit" in app.subprocesses.items[-1].detail


def test_app_handle_command_clear():
    from canary.app import CanaryApp
    app = CanaryApp()

    # Add some items
    app.subprocesses.add_item(app.subprocesses.__class__())
    app.handle_command("off")
    assert len(app.subprocesses.items) > 0

    # Clear should reset subprocesses
    result = app.handle_command("clear")
    assert result is True
    assert len(app.subprocesses.items) == 0


def test_app_handle_command_unknown():
    from canary.app import CanaryApp
    app = CanaryApp()

    result = app.handle_command("unknowncmd")
    assert result is True
    assert app.subprocesses.items[-1].status == "failed"
    assert "unknown" in app.subprocesses.items[-1].detail


def test_app_render_returns_renderable():
    from canary.app import CanaryApp
    from rich.console import Group

    app = CanaryApp()
    renderable = app.render()

    # Should return a Group
    assert isinstance(renderable, Group)


def test_app_submit_prompt_empty():
    from canary.app import CanaryApp
    app = CanaryApp()

    # Submit empty prompt should return early
    app.submit_prompt()
    # No subprocess items should be added for empty prompt
    assert len(app.subprocesses.items) == 0


def test_app_submit_prompt_adds_item():
    from canary.app import CanaryApp
    app = CanaryApp()

    app.set_prompt("test prompt")
    # With screening enabled, it will try to scan which requires local model
    # Just check that an item gets added before the scan
    app.submit_prompt()

    # Should have at least the prompt item
    assert len(app.subprocesses.items) >= 1
    assert "prompt:" in app.subprocesses.items[0].name
