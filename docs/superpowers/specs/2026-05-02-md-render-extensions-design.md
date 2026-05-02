# Docs markdown render extensions — design

Status: approved (brainstorm complete; implementation plan to follow)
Date: 2026-05-02
Scope: extend the siteapp markdown renderer to support GitHub-style
alerts, Mermaid flowcharts, raw inline `<img>` tags (and a small set of
other safe inline HTML), and doc-relative static assets such as icons.

## Problem

The siteapp renderer (`compose/siteapp/app/markdown.py`) is wired through
`markdown-it-py` with `html=False`, anchors, footnotes, tasklists, and a
Pygments-backed highlighter. Today it cleanly handles paragraphs, lists,
tables, fenced code, and headings — but four idioms used in the new
landing page are not supported:

- `> [!IMPORTANT]` (and the rest of the GitHub alert family —
  `NOTE`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`) render as a plain
  blockquote with the literal `[!IMPORTANT]` marker visible.
- ` ```mermaid ` fenced blocks render as escaped text (no diagram).
- `<img src="icons/jupyter.svg" …>` inside a markdown table is escaped
  to literal text because raw HTML is disabled at the parser.
- The relative `icons/jupyter.svg` URL has no file to resolve to —
  the `/docs/{path}` route only serves `.md`.

The trigger for this work is a richer `default_docs/index.md` that uses
all four. The desired rendered page mixes a hero callout, a flowchart of
how the VPS, the Windows agent and Loki/Grafana fit together, and a
table of "get started" rows where each row begins with a small product
icon. Without these features the page degrades into something that
reads worse than the current minimalist version.

## Goals

- Render `> [!TYPE]` blockquotes for the five GitHub alert types as a
  styled callout with a colored left border and a bold label, in plain
  CSS (no icons).
- Render `mermaid` fenced code blocks as live SVG diagrams, with no
  server-side Mermaid runtime.
- Allow a small fixed set of inline HTML tags — primarily `<img>` —
  with attribute filtering, so authors can drop product icons into
  tables and use the occasional `<kbd>`/`<sub>`/`<sup>`.
- Resolve doc-relative static assets (`icons/jupyter.svg` next to
  `index.md`) by serving them through the existing `/docs/{path}` route,
  with a hard extension allow-list and the same traversal protection
  the `.md` lookup already uses.
- Keep pages that don't use Mermaid completely free of Mermaid JS.
- Stay within the existing Docker image — no Node, no headless
  browser, no extra service.

## Non-goals

- Server-side Mermaid rendering (`mmdc`, Kroki, or similar). Diagrams
  render in the browser.
- Mermaid types beyond what the user-shipped runtime supports — we
  vendor the full `mermaid.min.js`, so whatever the runtime supports is
  what we support; no curation.
- Full HTML support. Raw HTML stays narrowly allow-listed; new tags
  must be added explicitly.
- Authoring UI for alerts or diagrams. Authors write markdown by hand,
  same as today.
- Rendering icons next to alert labels. Plain CSS only; we can add icons
  later in one place if the team decides they want them.
- Theming Mermaid beyond a light/dark switch driven by
  `prefers-color-scheme`.

## Architecture

The work touches three components and adds two static assets:

```
compose/siteapp/
├── app/
│   ├── markdown.py        ← +alert post-processor
│   │                        +mermaid highlighter branch
│   │                        +bleach sanitizer (html=True)
│   │                        +Rendered dataclass return
│   ├── docs.py            ← +doc-relative static file branch
│   ├── agent.py           ← updated to consume Rendered
│   ├── static/
│   │   ├── site.css       ← +alert styles, +mermaid reset
│   │   ├── mermaid-init.js   ← (new)
│   │   └── vendor/
│   │       └── mermaid.min.js ← (new, vendored release)
│   ├── templates/
│   │   └── base.html      ← conditional mermaid <script>
│   └── default_docs/
│       ├── index.md       ← updated to the richer version
│       └── icons/         ← (new) jupyter/windows/grafana/github SVGs
└── pyproject.toml         ← +bleach
```

### Render pipeline (after the change)

```
markdown text
   ↓
markdown-it-py parse  (html=True)
   ↓
_apply_alerts(tokens)  ← mutate blockquote_open/close in-place
   ↓
markdown-it-py render
   │  - fenced blocks pass through _highlight
   │     - lang == "mermaid"  → <pre class="mermaid">{escaped}</pre>
   │                            sets env["needs_mermaid"] = True
   │     - other langs        → existing Pygments path
   │  - raw inline HTML       → pass through (since html=True)
   ↓
bleach.clean(html, tags=…, attrs=…, protocols=…, strip=True)
   ↓
Rendered(html, title, needs_mermaid)
```

`Rendered` replaces today's `(html, title)` tuple. Two call sites
(`docs.py`, `agent.py`) update — both already destructure the tuple,
the change is mechanical.

### Why client-side Mermaid

Server-side rendering needs `mmdc` (Mermaid CLI), which pulls Node and
a headless Chromium into the siteapp image (~300 MB+) and adds a
subprocess call plus an SVG cache to manage. Kroki adds a whole
sidecar service. For one diagram on one page today, both options
overshoot. A vendored `mermaid.min.js` (~600 KB gzipped) is the
smallest moving-parts choice that works offline and does not depend on
any CDN; pages without diagrams pay zero JS cost because the script
tags only emit when `needs_mermaid` is true.

### Why bleach (over a custom rule)

`markdown-it-py` does not ship a sanitizer. The two real choices are
"trust the source and flip `html=True`" or "sanitize the output".
Authors here are operator-controlled, so the threat model is small,
but a one-line `bleach.clean(...)` with an explicit allow-list makes
the safety boundary visible in code review and shrinks the blast
radius if a future change ever pipes user input through
`render_markdown`. A custom markdown-it rule that pass-throughs only
`<img>` would work, but every new tag we want (`<kbd>`, `<details>`)
needs another patch; bleach turns it into a one-line allow-list edit.

### Why doc-relative for icons

The user-shipped `index.md` references `icons/jupyter.svg` as a
relative path. That convention matches mkdocs, Hugo, and most static
site generators; it lets an author drop an asset next to the doc that
uses it. The alternative — forcing absolute `/_static/...` paths —
breaks the convention and means the source file can't be authored or
previewed in tools (like a plain editor preview) that expect relative
asset paths. Extending the `/docs/{path}` route is small (one branch,
reuses `safe_join`, hard extension allow-list).

## Components

### 1. `app/markdown.py`

**Return type.** Replace the `(html, title)` tuple with a frozen
dataclass:

```python
@dataclass(frozen=True)
class Rendered:
    html: str
    title: str | None
    needs_mermaid: bool
```

**MarkdownIt config.** `html=True` (was False). Linkify and typographer
unchanged. Anchors, footnotes, tasklists unchanged.

**Mermaid highlighter branch.** Inside the existing `_highlight`
callback, special-case `name == "mermaid"`:

```python
if name == "mermaid":
    return f'<pre class="mermaid">{html_escape(code)}</pre>\n'
```

The Pygments path is untouched for every other language. The escape on
`code` is belt-and-suspenders — even though the diagram source is then
sanitized by bleach, escaping at the highlighter keeps the contract
("highlighters return safe HTML") intact.

`needs_mermaid` is determined by a small token walk between `parse` and
`render`: scan for any `fence` token whose `info.split(maxsplit=1)[0]`
is `"mermaid"`. The markdown-it-py 3.x highlighter signature is
`(code, name, attrs)` and does not receive the parser env, so a side
channel via env is not available; a one-pass token scan is the
cleanest equivalent and runs in negligible time.

**Alert post-processor.** New function `_apply_alerts(tokens)` runs
between `parse` and `render`. Algorithm:

1. Iterate `tokens` looking at `blockquote_open` at any nesting depth
   (`level` agnostic — markdown's `> [!X]` is allowed inside lists, etc.;
   GitHub does the same).
2. Look ahead inside the blockquote for the first `inline` token (i.e.,
   the inline content of the first paragraph in the blockquote).
3. Match its leading text against the regex
   `^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*(\n|$)`.
4. If matched: rewrite the `blockquote_open` and matching
   `blockquote_close` tokens to render as `<div class="alert
   alert-{type}">…</div>` (set `tag = "div"`, attrSet `class`); strip
   the marker line from the inline's `content` and prune any leading
   `text`+`softbreak` children that correspond to the marker.
5. If not matched, leave the token untouched.

A token-level transform avoids regex-on-source pitfalls (markers inside
fenced code or indented blocks can't false-positive because they were
never parsed as a blockquote in the first place).

**Bleach sanitizer.** Apply once, after `renderer.render(...)`, to the
final HTML string:

```python
ALLOWED_TAGS = {
    # Markdown produces these — keep them.
    "h1","h2","h3","h4","h5","h6","p","a","ul","ol","li","blockquote",
    "pre","code","table","thead","tbody","tr","th","td","hr","strong",
    "em","del","img","input","span","div",
    # Inline HTML we want to allow.
    "kbd","sub","sup","br","details","summary",
}
ALLOWED_ATTRS = {
    "a": {"href","title","rel","target"},
    "img": {"src","alt","width","height","title","loading"},
    "input": {"type","disabled","checked","class"},  # tasklists
    "li": {"class"},                          # tasklist <li class="task-list-item">
    "code": {"class"}, "pre": {"class"},      # highlighted code, mermaid
    "div": {"class"}, "span": {"class"},      # alerts, anchors
    "h1": {"id"},"h2": {"id"},"h3": {"id"},"h4": {"id"},
}
ALLOWED_PROTOCOLS = {"http","https"}  # plus relative — bleach allows that by default
bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS,
             protocols=ALLOWED_PROTOCOLS, strip=True)
```

The `class` allow-list on `pre`/`code`/`div`/`span` is there so the
existing highlighter output (`class="highlight"`,
`class="language-foo"`), the alert wrappers (`class="alert
alert-note"`, etc.), and the Mermaid wrapper (`class="mermaid"`) all
survive the pass. `strip=True` (vs `strip=False`) means disallowed tags
are removed entirely instead of escaped to text — quieter on the page.

### 2. `app/static/vendor/mermaid.min.js` (new, vendored)

Pinned release of `mermaid` (latest stable 11.x at implementation
time). Committed to git like any other static asset. No build step.
The exact version is recorded in a one-line comment at the top of
`mermaid.min.js` (and noted in the commit message) so future upgrades
are deliberate.

### 3. `app/static/mermaid-init.js` (new)

```js
import("/_static/vendor/mermaid.min.js").then(() => {
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  window.mermaid.initialize({
    startOnLoad: false,
    theme: dark ? "dark" : "default",
    securityLevel: "strict",
  });
  window.mermaid.run({ querySelector: "pre.mermaid" });
});
```

`securityLevel: "strict"` disables `<foreignObject>` HTML embeds inside
diagrams — keeps the XSS surface tight. We initialize manually
(`startOnLoad: false`) so the call happens once after the dynamic
import resolves.

### 4. `app/templates/base.html`

Conditionally include the Mermaid scripts. The view already has a
`needs_mermaid` value to pass into the template context.

```jinja
{% if needs_mermaid %}
  <script src="/_static/mermaid-init.js" type="module" defer></script>
{% endif %}
```

The vendor file is loaded by `mermaid-init.js` via dynamic import, so
only one `<script>` tag in the template is needed.

### 5. `app/docs.py` — doc-relative static branch

Today the route logic is: redirect to trailing slash if the URL is a
directory; otherwise look up a `.md` doc. Insert a new branch in
between: if the URL maps to an existing **non-`.md`** file inside
`docs_root` whose extension is in the allow-list, serve it as
`FileResponse`; otherwise fall through to the existing markdown lookup.

```python
DOC_STATIC_EXTS = {".svg",".png",".jpg",".jpeg",".gif",".webp"}

# After the directory-redirect block, before the find_doc call:
if path:
    try:
        candidate = safe_join(settings.docs_root, *[p for p in path.split("/") if p])
    except ValueError:
        return Response(status_code=404)
    if candidate.is_file() and candidate.suffix.lower() in DOC_STATIC_EXTS:
        return FileResponse(candidate)  # FileResponse picks media type from suffix
```

The directory-redirect block already computes `candidate`; the two can
be merged into a single resolution to avoid recomputing. `safe_join`
guarantees the path stays under `docs_root`, so traversal attempts
return 404. Files with disallowed extensions also 404 (no
information leak about whether the file exists).

### 6. `app/agent.py`

Updates the call site:

```python
result = render_markdown(c.read_text(encoding="utf-8"))
return result.html  # previously: html, _ = ...; return html
```

The agent page does not currently use Mermaid, so `needs_mermaid` is
read but discarded for now. If the page ever uses a diagram, the
template wiring is already in place.

### 7. `app/static/site.css`

**Alert styles** (~25 lines):

```css
.prose .alert {
  margin: 1em 0;
  padding: 12px 16px;
  border-left: 4px solid var(--alert-accent);
  border-radius: 6px;
  background: color-mix(in srgb, var(--alert-accent) 8%, var(--bg));
}
.prose .alert::before {
  content: var(--alert-label);
  display: block;
  font-weight: 600;
  color: var(--alert-accent);
  margin-bottom: 4px;
}
.prose .alert > :first-child { margin-top: 0; }
.prose .alert > :last-child  { margin-bottom: 0; }
.alert-note      { --alert-accent: #2855ff; --alert-label: "Note"; }
.alert-tip       { --alert-accent: #16a34a; --alert-label: "Tip"; }
.alert-important { --alert-accent: #8b5cf6; --alert-label: "Important"; }
.alert-warning   { --alert-accent: #d97706; --alert-label: "Warning"; }
.alert-caution   { --alert-accent: #dc2626; --alert-label: "Caution"; }
```

`color-mix` produces a tinted background that is light on light themes
and dark on dark themes without a duplicated `@media` block — the
accent is a fixed hue, only the mix base (`--bg`) flips.

**Mermaid reset** (~6 lines):

```css
.prose pre.mermaid {
  background: transparent;
  border: 0;
  padding: 0;
  text-align: center;
}
.prose pre.mermaid svg { max-width: 100%; height: auto; }
```

Without this, the existing `.prose pre` styling would draw a code-block
border around the diagram source while it loads (visible flash) and
leave odd padding once Mermaid replaces it with an SVG.

### 8. `default_docs/index.md` and `default_docs/icons/`

Replace the current `default_docs/index.md` with the user-supplied
version that uses all four features. Commit four SVGs under
`default_docs/icons/`: `jupyter.svg`, `windows.svg`, `grafana.svg`,
`github.svg`. The icons are simple official-mark SVGs sized for ~28 px
display.

## Data flow (concrete request)

`GET /docs/`:

1. `docs_path("")` → `find_doc(...)` → `default_docs/index.md`.
2. `render_markdown(text)` → `Rendered(html, title="🧬 lab-bridge",
   needs_mermaid=True)`.
3. Template renders with `needs_mermaid=True`, so `mermaid-init.js`
   `<script>` is included.
4. Browser parses HTML; sees four `<img src="icons/jupyter.svg">`
   (etc.) inside the table, requests them.
5. `GET /docs/icons/jupyter.svg` → docs route's static branch →
   `FileResponse(default_docs/icons/jupyter.svg)`.
6. `mermaid-init.js` dynamic-imports `mermaid.min.js`, initializes,
   replaces `<pre class="mermaid">` with the rendered SVG.

## Error handling

| Failure | Behavior |
| --- | --- |
| Mermaid syntax error | Mermaid renders an inline error box where the diagram would be. Server doesn't validate. |
| Unknown alert type, e.g. `[!FOO]` | Treated as a plain blockquote; the `[!FOO]` text remains visible. Not an error. |
| Disallowed HTML tag (`<script>`, `<iframe>`) | Stripped silently by bleach. |
| Disallowed `<img>` attribute (`onerror`, etc.) | Attribute stripped, tag kept. |
| Doc-static path traversal (`/docs/../etc/passwd`) | `safe_join` raises `ValueError` → 404. |
| Doc-static unknown extension | 404 (no existence leak). |
| Mermaid script fails to load (offline, blocked) | The diagram source stays visible inside the `<pre class="mermaid">` (it's HTML-escaped, so it renders as monospace text). Page is still usable. |

## Testing

`compose/siteapp/tests/test_markdown.py`:

- Each of the five alert types renders to `<div class="alert
  alert-{type}">` with the marker stripped.
- A plain blockquote (no marker) still renders as `<blockquote>`.
- An unknown alert type (`[!FOO]`) renders as a plain blockquote with
  the marker text intact.
- A `[!IMPORTANT]` marker inside a fenced code block is **not**
  transformed.
- `<img src="icons/foo.svg" width="28">` survives sanitization with
  attributes intact.
- `<img src="x" onerror="alert(1)">` keeps the tag, drops `onerror`.
- `<script>alert(1)</script>` is stripped (bleach replaces today's
  `test_raw_html_is_escaped` expectation: the markup no longer survives
  as escaped text — it's gone).
- A Mermaid block renders to exactly `<pre class="mermaid">{escaped
  source}</pre>` — content is HTML-escaped (e.g., `<` becomes `&lt;`).
- `render_markdown` returns `needs_mermaid=True` if and only if at
  least one ` ```mermaid ` block was rendered.
- The existing tests for headings, anchors, tables, fenced code,
  one-`<pre>`-per-block continue to pass unchanged.

`compose/siteapp/tests/test_routes_docs.py`:

- `GET /docs/icons/foo.svg` (with a fixture SVG in the temporary docs
  root) → 200, `image/svg+xml`, body bytes match the file.
- `GET /docs/icons/foo.exe` (with the file present) → 404.
- `GET /docs/../etc/passwd` → 404 (existing traversal protection).
- `GET /docs/icons/missing.svg` → 404.

No browser/E2E test for Mermaid rendering itself — that is the
upstream library's concern. We test that we emit the right markup; the
runtime takes it from there.

## Dependencies

`compose/siteapp/pyproject.toml` adds:

```toml
bleach>=6,<7
```

No Python dep for Mermaid. `app/static/vendor/mermaid.min.js` is
committed to git, pinned by filename to a specific release.

## Risks & open questions

- **Bleach + markdown-it interaction.** Bleach can normalize HTML in
  ways that surprise downstream consumers (e.g., empty tags, attribute
  ordering). The risk is small but real; the test suite covers the
  shapes we care about (`<img>` attrs, `<script>` strip,
  `class="highlight"` survival, `class="mermaid"` survival).
- **Mermaid bundle size.** `mermaid.min.js` is large (~600 KB gz at
  v11). It only loads on pages that use it, but if doc count grows a
  lot, we may want to switch to a smaller pinned version or split the
  bundle. Not a launch blocker.
- **Icon set scope.** Four icons today; if the docs sprout more, the
  `default_docs/icons/` directory becomes a small license-attribution
  surface. Out of scope — flagged for the implementation plan to keep
  attribution comments inside each SVG.
