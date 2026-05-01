from __future__ import annotations

import re
from html import unescape

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound


def _highlight(code: str, name: str | None, _attrs: object) -> str:
    try:
        lexer = get_lexer_by_name(name) if name else guess_lexer(code)
    except ClassNotFound:
        return ""  # markdown-it falls back to its default renderer
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


_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def _extract_title(markdown_text: str) -> str | None:
    m = _H1.search(markdown_text)
    return m.group(1).strip() if m else None


_MD = _make_md()


def render_markdown(text: str) -> tuple[str, str | None]:
    """Return (html, title). Title is the first H1's text, or None."""
    return _MD.render(text), _extract_title(text)


def pygments_css() -> str:
    """The CSS rules pygments needs for the chosen theme. Include in templates once."""
    return HtmlFormatter(cssclass="highlight").get_style_defs(".highlight")
