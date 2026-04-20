def test_header_panel_renders_logo():
    from canary.tui import HeaderPanel
    from rich.console import Console
    import io

    panel = HeaderPanel(version="0.1.3", cwd="/test/path")
    renderable = panel.render()

    # Capture the rendered output
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    console.print(renderable)
    text = console.file.getvalue()

    assert "CANARY" in text or "canary" in text.lower()
    assert "0.1.3" in text
    assert "/test/path" in text


def test_prompt_area_renders_with_rules():
    from canary.tui import PromptArea
    from rich.console import Console
    import io

    area = PromptArea(prompt="test prompt", cursor="_")
    renderable = area.render()

    # Capture the rendered output
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    console.print(renderable)
    text = console.file.getvalue()

    assert ">" in text
    assert "test prompt" in text
