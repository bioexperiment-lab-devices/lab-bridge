from __future__ import annotations

import pytest

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


def test_table_column_alignment_survives_sanitizer() -> None:
    """markdown-it emits style="text-align:..." on aligned <th>/<td>;
    bleach must keep it. The default index.md uses :-: alignment."""
    src = "| L | C | R |\n| :- | :-: | -: |\n| a | b | c |\n"
    r = render_markdown(src)
    assert "text-align:left" in r.html or 'style="text-align:left"' in r.html
    assert "text-align:center" in r.html or 'style="text-align:center"' in r.html
    assert "text-align:right" in r.html or 'style="text-align:right"' in r.html


def test_mermaid_block_renders_as_pre_mermaid() -> None:
    src = "```mermaid\nflowchart LR\n  A --> B\n```\n"
    r = render_markdown(src)
    assert '<pre class="mermaid">' in r.html
    # Source must be HTML-escaped before being placed in the DOM.
    assert "flowchart LR" in r.html


def test_mermaid_source_is_escaped() -> None:
    src = "```mermaid\nA[\"<script>\"] --> B\n```\n"
    r = render_markdown(src)
    assert "<script>" not in r.html
    assert "&lt;script&gt;" in r.html


def test_needs_mermaid_true_when_block_present() -> None:
    src = "intro\n\n```mermaid\nflowchart LR\n  A --> B\n```\n"
    r = render_markdown(src)
    assert r.needs_mermaid is True


def test_needs_mermaid_false_for_plain_doc() -> None:
    r = render_markdown("# Hello\n\nworld\n")
    assert r.needs_mermaid is False


def test_pygments_languages_unaffected_by_mermaid_branch() -> None:
    src = '```python\nprint("hi")\n```\n'
    r = render_markdown(src)
    assert 'class="highlight"' in r.html
    assert 'class="language-python"' in r.html


@pytest.mark.parametrize(
    "marker,cls",
    [
        ("NOTE", "alert-note"),
        ("TIP", "alert-tip"),
        ("IMPORTANT", "alert-important"),
        ("WARNING", "alert-warning"),
        ("CAUTION", "alert-caution"),
    ],
)
def test_alert_renders_for_each_type(marker: str, cls: str) -> None:
    src = f"> [!{marker}]\n> body text here\n"
    r = render_markdown(src)
    assert f'<div class="alert {cls}">' in r.html
    assert "body text here" in r.html
    # The marker line must be stripped from the rendered body.
    assert f"[!{marker}]" not in r.html


def test_plain_blockquote_unchanged() -> None:
    src = "> just a quote, no marker\n"
    r = render_markdown(src)
    assert "<blockquote>" in r.html
    assert "alert" not in r.html


def test_unknown_marker_leaves_blockquote() -> None:
    src = "> [!FOO]\n> body\n"
    r = render_markdown(src)
    assert "<blockquote>" in r.html
    # The marker text remains visible since we did not transform it.
    assert "[!FOO]" in r.html


def test_marker_inside_fenced_code_is_not_transformed() -> None:
    src = "```\n> [!IMPORTANT]\n> body\n```\n"
    r = render_markdown(src)
    assert '<div class="alert' not in r.html
    # Inside the code block, the literal marker text survives (escaped).
    assert "[!IMPORTANT]" in r.html


def test_alert_preserves_inline_formatting() -> None:
    src = "> [!IMPORTANT]\n> No data **leaves** the box.\n"
    r = render_markdown(src)
    assert '<div class="alert alert-important">' in r.html
    assert "<strong>leaves</strong>" in r.html


def test_alert_containing_img() -> None:
    """An <img> inside an alert body must survive both the alert
    post-processor (which mutates blockquote tokens) and the bleach
    sanitizer (which sees the resulting <div class="alert ..."> wrapper)."""
    src = '> [!NOTE]\n> <img src="icons/foo.svg" alt="x" width="28">\n'
    r = render_markdown(src)
    assert '<div class="alert alert-note">' in r.html
    assert '<img src="icons/foo.svg"' in r.html
    assert 'alt="x"' in r.html
    assert 'width="28"' in r.html
