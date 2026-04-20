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

    # Start with screening enabled
    app.screening_enabled = True
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
