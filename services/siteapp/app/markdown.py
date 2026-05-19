from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape as html_escape
from html import unescape

import bleach
from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.style import Style
from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String, Token
from pygments.util import ClassNotFound


class _CodeStyle(Style):
    """Code-block token palette.

    The code-block surface is always dark (see `.lb-code` in `site.css`),
    so we only ship one palette tuned for the dark background — the same
    colors the design uses for its `.lb-tok-*` classes.
    """

    default_style = ""
    background_color = "transparent"
    styles = {
        Token: "#E7E3D6",  # plain
        Keyword: "#C99CE8",  # purple
        Name.Function: "#8FB3E8",
        Name.Class: "#8FB3E8",
        Name.Builtin: "#8FB3E8",
        String: "#93D29D",  # green
        Number: "#E3C067",  # yellow
        Comment: "italic #6B6759",  # gray
        Operator: "#8FB3E8",  # blue
        Punctuation: "#8FB3E8",  # blue
    }


# --- bleach allow-list ------------------------------------------------------
# Tags markdown-it produces (kept) plus a small set of inline HTML we want
# authors to be able to use directly.
ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        # markdown-produced
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "a",
        "ul",
        "ol",
        "li",
        "blockquote",
        "pre",
        "code",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "hr",
        "strong",
        "em",
        "del",
        "img",
        "input",
        "span",
        "div",
        "section",
        # author-allowed inline HTML
        "kbd",
        "sub",
        "sup",
        "br",
        "details",
        "summary",
        # code block figure wrapper
        "figure",
        "figcaption",
        "button",
    }
)
ALLOWED_ATTRS: dict[str, set[str]] = {
    "a": {"href", "title", "rel", "target", "class"},
    "img": {"src", "alt", "width", "height", "title", "loading"},
    "input": {"type", "disabled", "checked", "class"},  # tasklists
    "li": {"class"},  # tasklists
    "code": {"class"},  # highlighted code
    "pre": {"class"},  # highlighter + mermaid
    "div": {"class"},  # alerts
    "span": {"class"},  # anchors
    "h1": {"id"},
    "h2": {"id"},
    "h3": {"id"},
    "h4": {"id"},
    "h5": {"id"},
    "h6": {"id"},
    "th": {"style"},  # column alignment
    "td": {"style"},  # column alignment
    "section": {"class"},  # footnotes
    "sup": {"class"},  # footnote-ref
    "figure": {"class", "data-lang"},
    "figcaption": {"class"},
    "button": {"class", "type", "aria-label"},
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


_TITLE_RE = re.compile(r'(?:title|file)\s*=\s*"([^"]+)"')


def _parse_title(attrs: object) -> str | None:
    if not isinstance(attrs, str):
        return None
    m = _TITLE_RE.search(attrs)
    return m.group(1) if m else None


def _highlight(code: str, name: str | None, attrs: object) -> str:
    """Return highlighted code wrapped in our own <figure> / <pre><code>.

    Special-cases `mermaid`: emit <pre class="mermaid"> with the source
    HTML-escaped, so the client-side mermaid runtime can pick it up
    without any chance of injecting markup into the page. Pygments is
    skipped for mermaid (the source is a diagram DSL, not code).

    The output MUST start with `<pre` or `<figure` — markdown-it auto-wraps
    any highlighter output that doesn't start with `<pre`, producing nested
    `<pre>` boxes. We wrap with a single <figure class="lb-code"> so the
    .highlight CSS still applies for syntax colors.
    """
    if name == "mermaid":
        return f'<pre class="mermaid">{html_escape(code)}</pre>\n'
    if not name:
        return ""  # let markdown-it fall back to its default (escapes content)
    try:
        lexer = get_lexer_by_name(name)
    except ClassNotFound:
        return ""
    formatter = HtmlFormatter(style=_CodeStyle, nowrap=True)
    inner = highlight(code, lexer, formatter).rstrip("\n")
    safe_lang = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    title = _parse_title(attrs)
    file_span = f'<span class="lb-code__file">{html_escape(title)}</span>' if title else ""
    return (
        f'<figure class="lb-code" data-lang="{safe_lang}">'
        f'<figcaption class="lb-code__head">'
        f'<span class="lb-code__lang">{safe_lang}</span>'
        f"{file_span}"
        f'<button class="lb-code__copy" type="button" aria-label="Copy code">Copy</button>'
        f"</figcaption>"
        f'<pre class="highlight"><code class="language-{safe_lang}">{inner}</code></pre>'
        f"</figure>\n"
    )


def _fence_renderer(self, tokens, idx, options, env) -> str:  # type: ignore[no-untyped-def]
    """Custom fence rule: delegates to _highlight and returns result directly.

    markdown-it's built-in fence renderer wraps the highlight output in a
    second <pre><code> if it doesn't start with ``<pre``.  Registering our
    own render rule avoids that unwanted wrapping when we emit ``<figure>``.
    """
    token = tokens[idx]
    info = token.info.strip() if token.info else ""
    lang_name = ""
    lang_attrs = ""
    if info:
        parts = info.split(maxsplit=1)
        lang_name = parts[0]
        if len(parts) == 2:
            lang_attrs = parts[1]
    result = _highlight(token.content, lang_name, lang_attrs)
    if result:
        return result
    return f"<pre><code>{html_escape(token.content)}</code></pre>\n"


def _make_md() -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})
        .enable(["table", "strikethrough"])
        .use(
            anchors_plugin,
            min_level=2,
            max_level=4,
            permalink=True,
            permalinkSymbol="#",
            slug_func=_slug,
        )
        .use(footnote_plugin)
        .use(tasklists_plugin, enabled=True)
    )
    md.add_render_rule("fence", _fence_renderer)
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


_ALERT_TYPES: frozenset[str] = frozenset({"NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"})
_ALERT_MARKER_RE = re.compile(r"^\[!(?P<type>NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*(?:\n|$)")


def _apply_alerts(tokens) -> None:
    """Rewrite GitHub-style alert blockquotes to <div class="alert alert-X">.

    For each blockquote whose first inline content begins with `[!TYPE]\\n`,
    where TYPE is one of NOTE/TIP/IMPORTANT/WARNING/CAUTION:
      * The blockquote_open / blockquote_close tokens are mutated in place
        to render as <div class="alert alert-{type}">…</div>.
      * The marker line is stripped from the inline content (both the
        `content` field and the corresponding leading children).

    Other blockquotes are untouched. Markers inside fenced code blocks
    cannot match because they are never parsed as blockquotes.
    """
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type != "blockquote_open":
            i += 1
            continue

        # Locate the first inline token inside this blockquote.
        # Structure: blockquote_open, paragraph_open, inline, paragraph_close,
        # ..., blockquote_close.
        inline_idx = None
        depth = 1
        j = i + 1
        while j < len(tokens):
            t = tokens[j]
            if t.type == "blockquote_open":
                depth += 1
            elif t.type == "blockquote_close":
                depth -= 1
                if depth == 0:
                    break
            elif t.type == "inline" and inline_idx is None:
                inline_idx = j
            j += 1
        close_idx = j  # blockquote_close index, or len(tokens) if malformed

        if inline_idx is None:
            i = close_idx + 1
            continue

        inline = tokens[inline_idx]
        m = _ALERT_MARKER_RE.match(inline.content)
        if not m:
            i = close_idx + 1
            continue

        alert_type = m.group("type").lower()

        # Strip the marker from the inline source.
        inline.content = inline.content[m.end() :]

        # Strip the matching leading children: the marker `text` token, plus
        # any `softbreak` / `hardbreak` directly after it. The surviving
        # children render as the body.
        if inline.children:
            new_children = list(inline.children)
            # Remove leading text token that contains the marker.
            if new_children and new_children[0].type == "text":
                # The marker text token's content equals "[!TYPE]" exactly
                # (markdown-it splits on softbreak).
                if new_children[0].content == f"[!{m.group('type')}]":
                    new_children.pop(0)
                    # Also drop the immediately-following softbreak/hardbreak.
                    if new_children and new_children[0].type in ("softbreak", "hardbreak"):
                        new_children.pop(0)
            inline.children = new_children

        # Mutate the blockquote_open token to render as <div class=...>.
        open_tok = tokens[i]
        open_tok.tag = "div"
        open_tok.attrSet("class", f"alert alert-{alert_type}")

        # Mutate the matching blockquote_close.
        if close_idx < len(tokens):
            close_tok = tokens[close_idx]
            close_tok.tag = "div"

        i = close_idx + 1


def _has_mermaid(tokens) -> bool:
    """True if any fenced code block declares language 'mermaid'.

    The markdown-it-py 3.x highlight callback signature is (code, name, attrs)
    and does not receive the parser env, so we cannot side-channel the flag
    out of the highlighter. A token walk is the cleanest equivalent and runs
    in negligible time (linear in token count).
    """
    for tok in tokens:
        if tok.type == "fence" and tok.info:
            first = tok.info.strip().split(maxsplit=1)[0]
            if first == "mermaid":
                return True
    return False


def render_markdown(text: str) -> Rendered:
    tokens = _MD.parse(text)
    _apply_alerts(tokens)
    title = _title_from_tokens(tokens)
    needs_mermaid = _has_mermaid(tokens)
    raw_html = _MD.renderer.render(tokens, _MD.options, {})
    # Rename the anchors_plugin hardcoded class to our design-system name.
    raw_html = raw_html.replace('class="header-anchor"', 'class="lb-anchor"')
    return Rendered(html=_sanitize(raw_html), title=title, needs_mermaid=needs_mermaid)


_PYGMENTS_BG_RE = re.compile(r"^\.highlight\s*\{[^}]*\}\s*$", re.MULTILINE)


def _theme_css(style: type[Style]) -> str:
    """Pygments style defs minus the embedded `.highlight { background: ... }`
    rule, which would otherwise override the page's own --code-bg variable."""
    css = HtmlFormatter(style=style, cssclass="highlight").get_style_defs(".highlight")
    return _PYGMENTS_BG_RE.sub("", css).strip()


def pygments_css() -> str:
    """Code-highlighting CSS. Code blocks live on a permanent dark surface
    (see `.lb-code` in `site.css`), so we ship a single dark palette rather
    than gating one variant behind `[data-theme="dark"]`."""
    return _theme_css(_CodeStyle) + "\n"
