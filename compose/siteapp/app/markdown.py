from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

import bleach
from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound


# --- bleach allow-list ------------------------------------------------------
# Tags markdown-it produces (kept) plus a small set of inline HTML we want
# authors to be able to use directly.
ALLOWED_TAGS: frozenset[str] = frozenset({
    # markdown-produced
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "a", "ul", "ol", "li", "blockquote",
    "pre", "code", "table", "thead", "tbody", "tr", "th", "td",
    "hr", "strong", "em", "del", "img", "input", "span", "div",
    "section",
    # author-allowed inline HTML
    "kbd", "sub", "sup", "br", "details", "summary",
})
ALLOWED_ATTRS: dict[str, set[str]] = {
    "a": {"href", "title", "rel", "target"},
    "img": {"src", "alt", "width", "height", "title", "loading"},
    "input": {"type", "disabled", "checked", "class"},  # tasklists
    "li": {"class"},                                     # tasklists
    "code": {"class"},                                   # highlighted code
    "pre": {"class"},                                    # highlighter + mermaid
    "div": {"class"},                                    # alerts
    "span": {"class"},                                   # anchors
    "h1": {"id"}, "h2": {"id"}, "h3": {"id"},
    "h4": {"id"}, "h5": {"id"}, "h6": {"id"},
    "th": {"style"},                                     # column alignment
    "td": {"style"},                                     # column alignment
    "section": {"class"},                                # footnotes
    "sup": {"class"},                                    # footnote-ref
}
ALLOWED_PROTOCOLS: frozenset[str] = frozenset({"http", "https"})  # plus relative

# Minimal CSS sanitizer: only passes through text-align used by markdown-it for
# aligned table columns (e.g. | :- | :-: | -: |).  bleach requires a
# css_sanitizer instance whenever "style" appears in ALLOWED_ATTRS — without
# one it silently clears every style value.
_TEXT_ALIGN_RE = re.compile(r"^text-align:\s*(left|center|right)\s*$")


class _TableAlignCSSsanitizer:
    """Pass through only 'text-align: left|center|right'; drop everything else."""

    def sanitize_css(self, style: str) -> str:
        return style if _TEXT_ALIGN_RE.match(style.strip()) else ""


def _highlight(code: str, name: str | None, _attrs: object) -> str:
    """Return highlighted code wrapped in our own <pre><code>.

    The output MUST start with `<pre` — markdown-it auto-wraps any
    highlighter output that doesn't, producing nested `<pre>` boxes that
    double-up padding and borders. We use `nowrap=True` to get just the
    Pygments spans, then wrap with a single <pre class="highlight"><code>
    so the .highlight CSS still applies for syntax colors.
    """
    if not name:
        return ""  # let markdown-it fall back to its default (escapes content)
    try:
        lexer = get_lexer_by_name(name)
    except ClassNotFound:
        return ""
    formatter = HtmlFormatter(nowrap=True)
    inner = highlight(code, lexer, formatter).rstrip("\n")
    safe_lang = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    return f'<pre class="highlight"><code class="language-{safe_lang}">{inner}</code></pre>\n'


def _make_md() -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})
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


@dataclass(frozen=True)
class Rendered:
    """Output of `render_markdown`.

    `needs_mermaid` is True iff the source contained at least one
    ` ```mermaid ` fenced block; the page template uses it to decide
    whether to load the vendored Mermaid JS bundle.
    """

    html: str
    title: str | None
    needs_mermaid: bool = False


_CSS_SANITIZER = _TableAlignCSSsanitizer()


def _sanitize(html: str) -> str:
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        css_sanitizer=_CSS_SANITIZER,
    )


def render_markdown(text: str) -> Rendered:
    tokens = _MD.parse(text)
    title = _title_from_tokens(tokens)
    raw_html = _MD.renderer.render(tokens, _MD.options, {})
    return Rendered(html=_sanitize(raw_html), title=title, needs_mermaid=False)


_PYGMENTS_BG_RE = re.compile(r"^\.highlight\s*\{[^}]*\}\s*$", re.MULTILINE)


def _theme_css(style: str) -> str:
    """Pygments style defs minus the embedded `.highlight { background: ... }`
    rule, which would otherwise override the page's own --code-bg variable."""
    css = HtmlFormatter(style=style, cssclass="highlight").get_style_defs(".highlight")
    return _PYGMENTS_BG_RE.sub("", css).strip()


def pygments_css() -> str:
    """Light + dark code-highlighting CSS. The dark variant is gated on
    `prefers-color-scheme: dark` so the colors track the rest of the site."""
    light = _theme_css("friendly")
    dark = _theme_css("github-dark")
    return f"{light}\n@media (prefers-color-scheme: dark) {{\n{dark}\n}}\n"
