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


def test_script_tag_is_stripped() -> None:
    """With html=True + bleach, raw <script> tags are removed entirely.
    The inner text may remain as content (bleach.strip=True), but the
    tag cannot execute."""
    r = render_markdown("<script>alert(1)</script>\n")
    assert "<script>" not in r.html
    assert "</script>" not in r.html


def test_iframe_is_stripped() -> None:
    r = render_markdown('<iframe src="http://evil"></iframe>\n')
    assert "<iframe" not in r.html


def test_img_with_allowed_attrs_survives() -> None:
    src = '<img src="icons/jupyter.svg" alt="JupyterLab" width="28">\n'
    r = render_markdown(src)
    assert '<img' in r.html
    assert 'src="icons/jupyter.svg"' in r.html
    assert 'alt="JupyterLab"' in r.html
    assert 'width="28"' in r.html


def test_img_disallowed_attr_is_stripped() -> None:
    src = '<img src="x.svg" onerror="alert(1)">\n'
    r = render_markdown(src)
    assert "<img" in r.html
    assert "onerror" not in r.html


def test_kbd_inline_passes() -> None:
    r = render_markdown("Press <kbd>Esc</kbd> to quit.\n")
    assert "<kbd>Esc</kbd>" in r.html


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
