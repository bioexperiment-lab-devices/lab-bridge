from __future__ import annotations

from app.markdown import render_markdown


def test_returns_html_and_title() -> None:
    html, title = render_markdown("# Hello\n\nworld\n")
    assert title == "Hello"
    assert "<h1" in html
    assert "world" in html


def test_no_h1_returns_none_title() -> None:
    html, title = render_markdown("plain paragraph\n")
    assert title is None
    assert "<p>plain paragraph" in html


def test_raw_html_is_escaped() -> None:
    # html=False in markdown-it: raw HTML in source is rendered as text.
    html, _ = render_markdown("<script>alert(1)</script>\n")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_fenced_code_is_highlighted() -> None:
    src = '```python\nprint("hi")\n```\n'
    html, _ = render_markdown(src)
    # Pygments wraps code in a <div class="highlight">.
    assert 'class="highlight"' in html


def test_table_renders() -> None:
    src = "| a | b |\n|---|---|\n| 1 | 2 |\n"
    html, _ = render_markdown(src)
    assert "<table" in html and "<td>1</td>" in html


def test_heading_anchor() -> None:
    src = "## My Section\n"
    html, _ = render_markdown(src)
    # mdit-py-plugins anchors gives id="my-section".
    assert 'id="my-section"' in html
