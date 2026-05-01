from __future__ import annotations

import re
from html import unescape

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound


def _highlight(code: str, name: str | None, _attrs: object) -> str:
    if not name:
        return ""  # let markdown-it fall back to its default (escapes content)
    try:
        lexer = get_lexer_by_name(name)
    except ClassNotFound:
        return ""
    formatter = HtmlFormatter(nowrap=False, cssclass="highlight")
    return highlight(code, lexer, formatter)


def _make_md() -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
        .enable(["table", "strikethrough"])
        .use(anchors_plugin, min_level=2, max_level=4, permalink=False, slug_func=_slug)
        .use(footnote_plugin)
        .use(tasklists_plugin, enabled=True)
    )
    md.options["highlight"] = _highlight
    return md


_SLUG_STRIP = re.compile(r"[^\w\s-]")
_SLUG_SPACE = re.compile(r"[\s_]+")


def _slug(s: str) -> str:
    s = unescape(s).strip().lower()
    s = _SLUG_STRIP.sub("", s)
    s = _SLUG_SPACE.sub("-", s)
    return s.strip("-")


_MD = _make_md()


def _inline_text(token) -> str:
    """Concatenate the rendered text of an inline token's children.

    `text` and `code_inline` carry their literal content; other tokens
    (em_open, strong_open, link_open, ...) are markup and contribute nothing
    on their own — their inner text is captured by sibling `text` children.
    """
    if not token.children:
        return token.content
    parts: list[str] = []
    for child in token.children:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
    return "".join(parts)


def _title_from_tokens(tokens) -> str | None:
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag == "h1":
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                content = _inline_text(tokens[i + 1]).strip()
                return content or None
            return None
    return None


def render_markdown(text: str) -> tuple[str, str | None]:
    """Return (html, title). Title is the first H1's text, or None."""
    tokens = _MD.parse(text)
    title = _title_from_tokens(tokens)
    html = _MD.renderer.render(tokens, _MD.options, {})
    return html, title


def pygments_css() -> str:
    """The CSS rules pygments needs for the chosen theme. Include in templates once."""
    return HtmlFormatter(cssclass="highlight").get_style_defs(".highlight")
