"""Regression checks for selectable text in the log viewer."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOG_VIEW = ROOT / "arm/ui/logs/templates/logview.html"
LOG_CSS = ROOT / "arm/ui/static/css/arm-modern.css"


def test_log_updates_preserve_existing_text_nodes():
    """Streaming log output should append text instead of replacing the full log."""
    template = LOG_VIEW.read_text(encoding="utf-8")

    assert "xhr.onprogress = updateLogOutput;" in template
    assert "output.firstChild.appendData(newContent);" in template
    assert "if (newText === displayedText)" in template
    assert "setInterval(" not in template


def test_log_output_is_selectable_without_wrapping_lines():
    """Log lines should behave like selectable plain text with horizontal overflow."""
    template = LOG_VIEW.read_text(encoding="utf-8")
    css = LOG_CSS.read_text(encoding="utf-8")

    assert 'class="arm-log-output"' in template
    assert 'tabindex="0"' in template
    assert ".arm-log-output {" in css
    assert "white-space: pre;" in css
    assert "user-select: text;" in css
    assert "-webkit-user-select: text;" in css


def test_tail_view_does_not_force_scroll_during_selection():
    """Auto-follow should pause while text is selected or the user scrolls up."""
    template = LOG_VIEW.read_text(encoding="utf-8")

    assert "const hasSelection = selection && !selection.isCollapsed;" in template
    assert "isAtBottom && !hasSelection" in template
