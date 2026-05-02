from __future__ import annotations

from app.markdown import render_markdown


def test_returns_html_and_title() -> None:
    r = render_markdown("# Hello\n\nworld\n")
    assert r.title == "Hello"
    assert "<h1" in r.html
    assert "world" in r.html


def test_no_h1_returns_none_title() -> None:
    r = render_markdown("plain paragraph\n")
    assert r.title is None
    assert "<p>plain paragraph" in r.html


def test_raw_html_is_escaped() -> None:
    # html=False in markdown-it: raw HTML in source is rendered as text.
    r = render_markdown("<script>alert(1)</script>\n")
    assert "<script>" not in r.html
    assert "&lt;script&gt;" in r.html


def test_fenced_code_is_highlighted() -> None:
    src = '```python\nprint("hi")\n```\n'
    r = render_markdown(src)
    assert 'class="highlight"' in r.html


def test_table_renders() -> None:
    src = "| a | b |\n|---|---|\n| 1 | 2 |\n"
    r = render_markdown(src)
    assert "<table" in r.html and "<td>1</td>" in r.html


def test_heading_anchor() -> None:
    src = "## My Section\n"
    r = render_markdown(src)
    assert 'id="my-section"' in r.html


def test_unknown_language_still_escapes() -> None:
    src = "```zzznotalang\n<script>alert(1)</script>\n```\n"
    r = render_markdown(src)
    assert "<script>" not in r.html
    assert "&lt;script&gt;" in r.html


def test_h1_inside_fenced_code_not_treated_as_title() -> None:
    src = "Intro paragraph.\n\n```\n# Not a title\n```\n"
    r = render_markdown(src)
    assert r.title is None


def test_h1_with_inline_code_extracts_rendered_text() -> None:
    r = render_markdown("# Use `pip install` carefully\n")
    assert r.title == "Use pip install carefully"


def test_highlighted_code_block_is_not_double_wrapped() -> None:
    """Markdown-it wraps any highlighter output that doesn't start with `<pre`
    in its own `<pre><code>`. Our highlighter must emit a single
    <pre class="highlight"> so markdown-it skips the wrap. Exactly one <pre>
    per fenced block."""
    src = '```python\nprint("hi")\n```\n'
    r = render_markdown(src)
    assert r.html.count("<pre") == 1
    assert r.html.count("</pre>") == 1
    assert '<pre class="highlight">' in r.html


def test_needs_mermaid_default_false() -> None:
    r = render_markdown("# Hello\n\nworld\n")
    assert r.needs_mermaid is False
