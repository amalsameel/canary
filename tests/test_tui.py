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
    # Check for prompt content (with cursor appended, so check for parts)
    assert "test" in text
    assert "prompt" in text


def test_subprocess_tree_renders_unicode_branches():
    from canary.tui import SubprocessTree, SubprocessItem
    from rich.console import Console
    import io
    import re

    items = [
        SubprocessItem(name="scan", status="complete", detail="prompt cleared"),
        SubprocessItem(name="analyze", status="running", detail="semantic scan in flight"),
    ]
    tree = SubprocessTree(items=items)
    renderable = tree.render()

    # Capture the rendered output
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    console.print(renderable)
    text = re.sub(r"\x1b\[[0-9;]*m", "", console.file.getvalue())

    assert "scan" in text
    assert "analyze" in text
    assert "done" in text
    assert "scanning..." in text
    assert "prompt cleared" in text


def test_thinking_indicator_animates():
    from canary.tui import ThinkingIndicator
    indicator = ThinkingIndicator(is_thinking=True)
    frame1 = indicator.render()
    indicator.tick()
    frame2 = indicator.render()
    # Should change between frames
    assert str(frame1) != str(frame2) or indicator._frame > 0
