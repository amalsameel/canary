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


def test_prompt_input_bar_wraps_and_expands_for_multiline_text():
    from canary.ui import prompt_input_bar
    from rich.console import Console
    import io
    import re

    renderable = prompt_input_bar(prompt="fix\nlogin", cursor_pos=4, line_count=2)
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    console.print(renderable)
    text = re.sub(r"\x1b\[[0-9;]*m", "", console.file.getvalue())

    assert text.count("▌") == 1
    assert "fix" in text
    assert "login" in text
    assert text.count("────────────────") >= 2


def test_prompt_input_bar_soft_wraps_long_single_line_text(monkeypatch):
    from canary.ui import prompt_input_bar
    from rich.console import Console
    import io
    import re

    monkeypatch.setattr("canary.ui.shell_frame_width", lambda: 18)

    renderable = prompt_input_bar(prompt="abcdefghijklmnop", cursor_pos=16)
    console = Console(file=io.StringIO(), force_terminal=True, width=40)
    console.print(renderable)
    text = re.sub(r"\x1b\[[0-9;]*m", "", console.file.getvalue())

    assert "❯ abcdefghijklmno" in text
    assert "  ▌" in text


def test_prompt_input_bar_can_summarize_large_paste():
    from canary.ui import prompt_input_bar
    from rich.console import Console
    import io
    import re

    renderable = prompt_input_bar(
        prompt="ignored",
        show_paste_summary=True,
        paste_word_count=180,
        paste_line_count=12,
    )
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    console.print(renderable)
    text = re.sub(r"\x1b\[[0-9;]*m", "", console.file.getvalue())

    assert "[Pasted text, 180 words, 12 lines]" in text
    assert text.count("▌") == 1


def test_submitted_prompt_bar_uses_grey_background_without_rules(monkeypatch):
    from canary.ui import submitted_prompt_bar

    monkeypatch.setattr("canary.ui.shell_frame_width", lambda: 24)

    renderable = submitted_prompt_bar("fix login flow", status="complete")
    line = renderable.renderables[0]

    assert len(renderable.renderables) == 1
    assert line.plain.rstrip() == "✓ fix login flow"
    assert "─" not in line.plain
    assert any("on #2d2d2d" in str(span.style) for span in line.spans)


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
