# Platform UI hi-fi redesign — navbar, Home, Download, Docs

**Status:** draft
**Date:** 2026-05-19
**Owners:** platform
**Design handoff:** `docs/design_handoff_lab_bridge/`

## Goal

Apply the hi-fi design from the lab-bridge handoff to four surfaces — the
shared platform navbar (already in production, visuals only) and the three
siteapp pages (Home, Download Agent, Docs) — as a single coordinated change.
Pixel-perfect: tokens, typography, spacing, copy and interaction states come
from the handoff verbatim. Architecture is unchanged: the shared navbar stays
a Caddy-injected vanilla web component at `compose/shell/navbar.js`; siteapp
stays FastAPI + Jinja + plain CSS, no build step.

The 2026-05-17 shared-navbar spec defined the architecture; this spec defines
the visual + content layer that lives on top of it, plus the missing backend
piece for the Home lab-status panel.

## Surfaces in scope

1. **Platform navbar** — three modes (expanded rail / collapsed rail /
   bookmark tab + overlay). Visual rewrite plus a theme toggle and a brand row
   with platform-version pill.
2. **Home** — `/` — sticky header, statement headline, live lab-status panel,
   static topology diagram, quick-destinations grid, getting-started grid.
   EN/RU bilingual.
3. **Download Agent** — `/download/agent` — sticky header, SerialHop hero,
   three platform cards (Windows = available; Linux + RPi = coming-soon),
   browser-block explainer, version metadata with SHA-256 copy.
   EN/RU bilingual.
4. **Docs** — `/docs/*` — restyled MkDocs-Material-feel sidebar + article,
   code-block header bar with filename, 5-flavor admonitions, breadcrumb +
   prev/next nav, EN/RU toggle (already wired in routing).

## Architecture overview

```
┌─ compose/shell/ (platform-only, served by Caddy at /_shared/*) ─────┐
│  navbar.js         — <lds-navbar> custom element, Shadow DOM       │
│  navbar-inner.css  — Shadow-DOM styles, duplicates design tokens   │
└────────────────────────────────────────────────────────────────────┘
              │ injected by Caddy on every text/html response
              ▼
┌─ services/siteapp/ ─────────────────────────────────────────────────┐
│  app/static/                                                        │
│    tokens.css      (new) — design tokens (light + [data-theme=…])  │
│    site.css        (rewrite) — page styles, imports tokens         │
│    copy-inline.js  (new) — single click-to-copy utility            │
│    copy-code.js    (slim down) — delegate to copy-inline           │
│  app/templates/                                                    │
│    base.html       — IBM Plex fonts, theme boot script             │
│    home.html       — rebuild + _home_*.html partials               │
│    agent.html      — rebuild + _dl_*.html partials                 │
│    doc.html        — restyle + breadcrumb / prev-next              │
│    _nav.html       — restyle sidebar                               │
│  app/                                                              │
│    home.py         — lang resolver, initial-labs render            │
│    agent.py        — _relative_time helper                         │
│    docs.py         — breadcrumb + prev/next helpers                │
│    labs.py         (new) — /api/public/labs aggregator             │
│    strings.py      (new) — HOME_STRINGS + DL_STRINGS (EN + RU)     │
│    markdown.py     — fenced-block title= attr, custom pygments     │
│  tests/                                                            │
│    test_labs.py            (new)                                   │
│    test_strings.py         (new)                                   │
│    test_markdown.py        (extend)                                │
│    test_agent.py           (extend)                                │
│    e2e/test_home_page.py   (new)                                   │
│    e2e/test_download_page.py (new)                                 │
│    e2e/test_docs_page.py   (extend)                                │
└────────────────────────────────────────────────────────────────────┘

┌─ compose/ ──────────────────────────────────────────────────────────┐
│  Caddyfile.tmpl   — inject data-version attr on /_shared/navbar.js │
└────────────────────────────────────────────────────────────────────┘

┌─ public_docs/ ──────────────────────────────────────────────────────┐
│  researcher/  operator/  admin/  reference/  — stub sections       │
│  (existing system-overview.md, technical-overview.md stay at root) │
└────────────────────────────────────────────────────────────────────┘
```

## Design tokens

All colors, shadows, type scale, spacing and radii come verbatim from the
handoff's "Design tokens" section (`docs/design_handoff_lab_bridge/README.md`
lines 48–145). They are not re-listed here — that document is authoritative.

Tokens live in two places by necessity:

1. **`services/siteapp/app/static/tokens.css`** — `:root` (light defaults) +
   `[data-theme="dark"]` (dark overrides). Imported once by `site.css`.
2. **`compose/shell/navbar-inner.css`** — `:host` (light defaults) +
   `:host([data-theme="dark"])` (dark overrides). Same values. Duplicated so
   the navbar's Shadow DOM is fully self-contained regardless of host-page
   CSS (Jupyter / Grafana).

If a token changes, edit both files in lockstep. A line-count diff between
the two `:root` / `:host` blocks should match modulo selector prefix.

### Type system

- Font stack: `'IBM Plex Sans', system-ui, sans-serif` for UI;
  `'IBM Plex Mono', ui-monospace, monospace` for lab names, versions, paths,
  code, eyebrow tags.
- Loaded from Google Fonts CDN via two `<link rel="preconnect">` + one
  `<link rel="stylesheet">` in `base.html`. Weights: 400/500/600/700 sans,
  400/500/600 mono. (Self-hosting is deferred to a follow-up if FOUC or
  privacy concerns surface.)
- Base body: `font-size: 13px; line-height: 1.45`. Pages override per the
  type-scale table in the handoff (Home headline 26px, docs H1 32px, etc.).

### Theme model

- `<html>` carries `data-theme="light"` or `data-theme="dark"`. CSS in both
  `tokens.css` and `navbar-inner.css` observes this attribute. No
  `prefers-color-scheme` media query is used at the token level.
- Source of truth: `localStorage['theme']`. Cross-tab sync via the native
  `storage` event.
- Boot script (inline in `base.html` `<head>`, runs before paint):

  ```js
  (function () {
    var t = localStorage.getItem('theme');
    if (!t) t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    document.documentElement.dataset.theme = t;
  })();
  ```

- Toggle (lives inside the navbar Shadow DOM, see Navbar section):
  on click, writes `localStorage['theme']`, manually applies
  `document.documentElement.dataset.theme = newTheme` (since the originating
  tab gets no `storage` event), updates `:host` attribute on the navbar
  element.
- Scope: theme attribute lives on `<html>`, so it only applies to
  siteapp-rendered pages. Jupyter / Grafana ignore the attribute — their UIs
  follow their own theme settings. The navbar inside Jupyter / Grafana
  (bookmark mode) does not show the theme toggle — see Navbar section.

## Shared utilities

### `services/siteapp/app/strings.py` (new)

```python
from typing import Literal

Lang = Literal["en", "ru"]

HOME_STRINGS: dict[Lang, dict[str, str]] = {
    "en": {
        "tagline": "lab instrumentation platform",
        "intro_eyebrow": "WHAT LAB-BRIDGE IS",
        "intro_headline": "One bridge from every lab instrument to the researchers using it.",
        # …all keys from lab-bridge-home.jsx STRINGS.en…
    },
    "ru": {
        # …mirror of EN, designer-written; see Risks…
    },
}

DL_STRINGS: dict[Lang, dict[str, str]] = {
    "en": {
        "hero_title": "SerialHop",
        "hero_lede": "Single-binary agent that exposes a lab PC's instruments to lab-bridge through a secure reverse tunnel.",
        # …all keys from lab-bridge-download.jsx DL_STRINGS.en…
    },
    "ru": {
        # …mirror of EN…
    },
}
```

Browser-block explainer copy on the Download page is **markup-heavy** (`<ol>`
+ `<kbd>` + `<code>` + bold quoted button labels in two languages). It stays
inside `templates/_dl_explainer.html` rather than this dict — already
bilingual there in today's `agent.html` and easier to maintain as markup.

### `services/siteapp/app/static/copy-inline.js` (new)

Single click-to-copy utility used by lab-status rows (Home), SHA-256
(Download), and code blocks (Docs). Wires to elements with
`data-copy-text="…"` or `data-copy-from="<selector>"`, writes to clipboard,
toggles `.is-copied` for 1.5s.

Today's `copy-code.js` injects the Copy button into every `<pre>` at runtime.
That responsibility moves server-side: the Markdown layer (see Docs section)
emits `<button class="lb-code__copy">` as part of the rendered HTML. The
remaining client-side concern is just the click handler — handled by
`copy-inline.js`. `copy-code.js` is removed.

Roughly 20–30 lines. Single observer pattern, idempotent on duplicate
include.

## Navbar (`compose/shell/`)

### Logic that stays

- `<lds-navbar>` custom element, open Shadow DOM
- Single-mount + MutationObserver re-attach
- `SERVICES` array, `PATH_RULES` mode detection by longest-prefix
- Persistent collapsed/expanded state machine, `localStorage['navbar:state']`
- Bookmark hover (150ms in / 300ms leave), Esc + backdrop dismiss
- `--nav-width` CSS variable for content reflow

### Logic that changes

- **Widths:** collapsed rail `52px → 56px`, expanded rail `240px → 220px`
  (handoff values).
- **Brand row** at top of rail (56px tall):
  - 28×28 brand mark (CSS-composed accent square with inner bracket+circle
    motif; SVG fallback acceptable if CSS reproduction is fiddly).
  - "lab-bridge" wordmark (15px, weight 600).
  - Version pill in mono uppercase (e.g. `v0.9.0`), read from the
    `data-version` attribute on the injected `<script>` tag (see Caddyfile
    change below).
  - Collapsed state shows brand mark only, centered.
- **Theme toggle** button, bottom of rail above the chevron:
  - Sun/moon icon + label `Light` / `Dark`.
  - On click: writes `localStorage['theme']`, applies
    `document.documentElement.dataset.theme`, updates `:host` attribute.
  - Collapsed: icon-only square.
  - Hidden in bookmark mode (theme scope is siteapp-owned pages only).
- **Bookmark tab redesign:**
  - 132×32 labeled tab pinned `left: 12px; bottom: 12px`.
  - Brand mark + "lab-bridge" wordmark + `›` chevron.
  - Hover → 240px popover (not full-rail) floating above viewport, all 6 nav
    items + theme toggle + "Esc to dismiss" hint at bottom.
  - Replaces today's accent-stripe-only tab.
- **Icons:** replace generic monoline set with the handoff's hand-rolled SVGs
  (18×18 viewBox, stroke-width 1.5, `currentColor`). Copy SVG paths verbatim
  from `lab-bridge-navbar.jsx`'s `Icons` object.
- **External-link indicator:** `↗` Unicode (10px mono, muted) after labels
  for JupyterLab / Grafana / Flasher.
- **Active item:** accent left bar via `::before` (4px wide), accent-soft
  background, accent icon color, 600 weight.

### `compose/shell/navbar-inner.css` rewrite

- Duplicates the design tokens block from `tokens.css` (both light + dark
  variants on `:host` selectors).
- All `.lb-rail*` and `.lb-bookmark*` rules ported from
  `docs/design_handoff_lab_bridge/source/lab-bridge-styles.css`.
- Width transition: `200ms cubic-bezier(.2,.7,.3,1)` (handoff easing).
- Backdrop dim: `rgba(26,25,22,0.18)` light, slightly darker dark variant.
- Expanded-rail drop shadow uses `var(--shadow-overlay)`.

### `compose/Caddyfile.tmpl` change

One-line addition: `data-version` attribute on the injected `<script>` tag,
populated by the existing `__PLATFORM_VERSION__` substitution.

Before:

```caddyfile
"</head>" `<script src="/_shared/navbar.js?v=__PLATFORM_VERSION__" defer></script></head>`
```

After:

```caddyfile
"</head>" `<script src="/_shared/navbar.js?v=__PLATFORM_VERSION__" data-version="__PLATFORM_VERSION__" defer></script></head>`
```

No changes to `scripts/lib/render.sh` — the existing `_unified_version`
substitution rewrites both occurrences.

## Home page (`/`)

### Route changes (`app/home.py`)

- Read `lang` query param + cookie (mirror `_pick_lang` from `app/docs.py`).
- Resolve `HOME_STRINGS[lang]`.
- Synchronously call `labs.aggregate_labs(settings)` once at render time so
  the panel arrives populated (no loading-flash). Pass `labs_initial` to
  template.
- Set `lang` cookie when query param was provided (1-year max-age, samesite
  lax, secure, httponly).

### Backend: `services/siteapp/app/labs.py` (new)

New module + route registered in `app/main.py`:

```python
@router.get("/api/public/labs")
async def list_labs() -> list[LabRow]:
    return await aggregate_labs(settings)
```

`LabRow` (Pydantic / TypedDict):

```python
class LabRow(TypedDict):
    name: str
    online: bool
    version: NotRequired[str]   # only when online and /agent/info succeeded
    hostname: NotRequired[str]
    outdated: NotRequired[bool] # only when version present AND latest known
```

`aggregate_labs(settings)`:

1. Load roster via existing `load_roster(settings.clients_file)` →
   `{name: {host, port}}`.
2. In parallel via `asyncio.gather`, per lab:
   `await httpx.AsyncClient.get(f"http://{host}:{port}/agent/info",
   timeout=0.8)`.
3. Per-lab error / timeout / non-200 / malformed JSON → `{name,
   online: False}`.
4. Successful → `{name, online: True, version, hostname, outdated}` where
   `outdated` is computed by version comparison (see below).
5. Sort: online first (alphabetical), then offline (alphabetical).
6. Cache result in process-local dict with `(timestamp, list[LabRow])` for
   60 seconds. Concurrent requests during refresh wait on a single
   `asyncio.Lock`.

Version comparison for `outdated`:

- `latest = load_meta(settings.agent_root).version` (the agent currently
  uploaded by an operator; already in `meta.json`).
- If `meta.json` missing → no `outdated` field on any row.
- Strip `+build_sha` suffix from both `version` and `latest`.
- Use `packaging.version.Version` (transitive dep of FastAPI / uvicorn). If
  either side raises `InvalidVersion` → no `outdated` field on that row.
- Lab is outdated iff `Version(lab) < Version(latest)`.

### Template structure

```
templates/
├─ home.html                — shell, language plumbing
├─ _home_header.html        — sticky header + EN/RU toggle
├─ _home_intro.html         — statement-headline card
├─ _home_status_row.html    — 2-col grid wrapper
│   ├─ _home_labs.html      — online/offline groups + rows
│   └─ _home_topology.html  — 3-node static diagram
├─ _home_quick.html         — 4-card grid
└─ _home_start.html         — 2-card grid (researcher + operator)
```

### Per-section detail

- **Sticky header** (`.lb-home-header`): accent dot + "lab-bridge" wordmark
  + vertical rule + tagline (mono uppercase). EN/RU pill toggle on the right
  (segmented control, mono uppercase, 11px). Scroll-shadow via small
  `IntersectionObserver` (~12 lines) — turn on only when content scrolls
  beneath.
- **Statement headline** (`.lb-intro-stmt`): bordered warm-cream card,
  3px accent left stripe, eyebrow pill (`WHAT LAB-BRIDGE IS`, accent fill,
  white text), 26px sans headline, support paragraphs in 1.6fr/1fr grid.
- **Lab status panel** (`.lb-equip`): max-width 560px, panel head
  (`Registered labs` + `updated Ns ago` meta), two groups with
  bordered-top headers `ONLINE · N` / `OFFLINE · N`. Rows:
  status dot (8px circle), mono lab name (13px, 600), optional
  OUTDATED pill (warning yellow, 9.5px mono uppercase) with tooltip
  "This lab is on an older SerialHop than the rest of the fleet",
  mono version (11.5px muted). Offline rows: name color
  `--text-secondary`, no version shown. Client-side: 5s poll updates
  the panel and the "updated Ns ago" counter.
- **Topology diagram** (`.lb-topo-section`): max-width 280px, static
  three-card stack (Lab PC → lab-bridge → Researcher) with dotted vertical
  lines + downward arrowhead glyphs. Middle node emphasized with
  `--accent-soft` background. **Not sticky** in v1 (handoff warned about
  fighting the page header).
- **Quick destinations** (`.lb-quick`): 4-card grid. JupyterLab is primary
  (`data-primary="true"`: accent-soft bg, accent-tinted icon, `↗` external
  arrow). Other three (Browse docs, Download agent, Grafana) on neutral
  surface. Card content: 24×24 icon tile + title + arrow + muted-mono path.
- **Getting started** (`.lb-start`): 2-card grid. Researcher card
  (`accent` dot) → `/docs/researcher/first-notebook`. Operator card
  (`warning` dot) → `/docs/operator/setup-lab-pc`. Each: role pill + 15px
  title + description + muted-mono path + 28×28 chevron top-right that
  fills/slides on hover.

### Lang toggle

EN/RU pill links `?lang=en` / `?lang=ru` — same pattern as docs. Server-side
re-render. No JS needed.

### Copy-to-clipboard on lab names

`.lb-labrow` rendered as `<button data-copy-text="{{ lab.name }}">` for
keyboard a11y. `copy-inline.js` handles the click.

## Download page (`/download/agent`)

### Route changes (`app/agent.py`)

- New helper `_relative_time(iso: str, lang: Lang) -> str`:
  pure function over `datetime.fromisoformat(iso)` and `datetime.now(UTC)`,
  returns localized "just now" / "5 minutes ago" / "2 hours ago" /
  "6 days ago" / "3 weeks ago". RU forms in `DL_STRINGS`.
- Template context grows: `released_relative` alongside `info.uploaded_at`.
- `AgentInfo` dataclass + `load_meta()` unchanged.
- Build-not-yet-uploaded edge case: `info is None` → template renders
  Windows card with disabled "Not yet available — check back soon" CTA,
  hides explainer + metadata. Coming-soon cards still render.

### Template structure

```
templates/
├─ agent.html              — shell, language plumbing
├─ _home_header.html       — reused (same sticky header + EN/RU toggle)
├─ _dl_hero.html           — 56×56 logo + SerialHop mono title + lede + GH link
├─ _dl_card_windows.html   — always-rendered, available-or-disabled
│   ├─ _dl_cta.html
│   ├─ _dl_explainer.html  — bilingual <details>, browser-block walkthrough
│   └─ _dl_meta.html       — version/released/sha + COPY button
├─ _dl_card_coming.html    — generic coming-soon, reused for Linux + RPi
└─ _dl_body_md.html        — operator Markdown, omitted if absent
```

### Platform cards

| Card | Source | Visual |
|---|---|---|
| Windows | `AgentInfo` from `meta.json` when present | Available: `--border-strong`, `--shadow-card`, green status pill, full CTA, explainer, metadata. No-build: disabled pill button, card visible, explainer + metadata hidden. |
| Linux | Static template | Coming soon: `--border` dashed, `--surface-sunken` bg, icon opacity 0.7, muted "Coming soon" pill, "expected Q3 2026" ETA. No body. |
| Raspberry Pi | Static template | Same pattern, "expected Q4 2026". |

ETAs hard-coded in the template; edit + ship when reality changes.

### Hero

- 56×56 accent-filled logo glyph (stylized "S" plug).
- Title: `SerialHop` in **mono** (`IBM Plex Mono`), 30px, weight 600.
- Lede: one sentence (EN + RU in `DL_STRINGS`).
- Source link: muted mono → `github.com/bioexperiment-lab-devices/serialhop`
  with dotted underline; hover → accent.

### CTA

Full-width accent-filled button:
- Line 1: "Download for Windows" (16px, weight 600).
- Line 2: `v{version} · {size_mb} MB` (mono 11px, opacity 0.85).
- `href="/download/agent/windows/agent.exe"` (existing route, filename
  rewrite `SerialHop-v{version}.exe` is already in place).

### Browser-block explainer

Native `<details>`, collapsed by default. Summary: warning-tinted bar with
circular `!` icon, summary text, `▾` chevron rotating `-180deg` when open.
Body: two H4 step groups in mono-uppercase warning color, numbered `<ol>`
with `<kbd>` chips, `<code>` chips, bold quoted button labels.

The bilingual copy (full EN + RU text of both step groups) already exists in
today's `services/siteapp/app/templates/agent.html`. The rewrite moves that
markup verbatim into `_dl_explainer.html` and applies the new design's CSS
classes — no copy changes, no translation work.

### Version metadata

Sunken stripe `<dl>`:
- `Version` → `<code>` chip with version.
- `Released` → ISO timestamp + muted "6 days ago".
- `SHA-256` → 64-char hex in `<code style="user-select: all">` + small COPY
  button (`copy-inline.js`).

### Optional Markdown body

Existing `_body_markdown(agent_root, lang)` already handles
`page.md` / `page.ru.md`. Rendered inside `.lb-dl-bodymd` using docs article
primitives. When `body_html is None`, the entire section is omitted.

## Docs (`/docs/*`)

### Markdown layer changes (`app/markdown.py`)

1. **Fenced-block `title=` attribute:**
   `_highlight(code, name, attrs)` parses `attrs` for `title="…"` (alias:
   `file="…"`). Emits:

   ```html
   <figure class="lb-code" data-lang="python">
     <figcaption class="lb-code__head">
       <span class="lb-code__lang">python</span>
       <span class="lb-code__file">serialhop/cli.py</span>
       <button class="lb-code__copy" type="button" aria-label="Copy code">Copy</button>
     </figcaption>
     <pre class="highlight"><code class="language-python">…</code></pre>
   </figure>
   ```

   No `title=` → omit `.lb-code__file` span. Bleach allow-list updates: add
   `figure`, `figcaption`, `button` to `ALLOWED_TAGS`; add `class` /
   `data-lang` / `type` / `aria-label` to per-tag attr lists as needed.

2. **Custom Pygments style:**
   Replace stdlib `friendly` (light) + `github-dark` (dark) styles with two
   small custom `pygments.style.Style` subclasses (~30 lines each) that map
   token types to the handoff's intended colors (keys/purple, strings/green,
   numbers/yellow, comments/italic-gray, operators/blue). `pygments_css()`
   emits both, wraps the dark variant in `[data-theme="dark"] { … }`
   selector instead of today's `@media (prefers-color-scheme: dark)`.

3. **Anchor permalinks:**
   `anchors_plugin(permalink=True, permalinkSymbol="#",
   permalinkClass="lb-anchor")`. CSS hides `.lb-anchor` by default, reveals
   on heading hover (muted color).

### Template + route changes

- **`templates/doc.html`:** 256px sidebar + max-720px article, 32–48px article
  padding. Article structure:
  1. Breadcrumb (mono muted, " / " separators).
  2. EN/RU toggle (top-right) — only when `doc.ru_exists`.
  3. H1 (already from rendered HTML).
  4. Content (rendered HTML).
  5. Prev/Next footer (2-col flex).
- **`templates/_nav.html`:** restyled. "Documentation" header with docs icon
  (mono uppercase). Top-level directory entries render as section group
  headers (mono uppercase). 13px sans items, 5px accent left border on
  active, accent-soft background on active. Folder rows get `›` prefix
  flipping to `⌄` when open. `[RU]` pill on right of items with translation.
- **`app/docs.py`:** add `build_breadcrumb(nav, current_url) ->
  list[BreadcrumbCrumb]` and `prev_next(nav, current_url) ->
  tuple[NavEntry | None, NavEntry | None]`. Both pure functions over the
  nav tree. Pass results to template.

### Sidebar interactivity

Tiny client script (~25 lines): clicking a folder row toggles its `<ul>`
collapsed/expanded, persists per-section state in
`localStorage['docs-nav:<url>']`. Active item's ancestor sections auto-open
on page load.

### Article styling

- **Inline code:** `--surface-sunken` bg, `--accent` text, mono 13px.
- **Code blocks:** dark surface (`#1A1916`) regardless of page theme
  (handoff explicit). Header bar uses `--text-inverse` for labels.
- **Tables:** `border-collapse`, mono-uppercase header in `--surface-strip`,
  `<code>` in cells accent-colored.
- **Lists:** 14.5px line-height 1.65.
- **Links:** accent text, `var(--accent-border)` underline,
  hover → `--accent-hover`.

### 5 admonition flavors

`_apply_alerts` already emits `<div class="alert alert-{kind}">`. CSS rewrite
to design tokens: 28px-wide left column with circular icon + body.

| Kind | Border / fill | Icon glyph |
|---|---|---|
| note | accent | `i` |
| tip | success | `i` |
| important | `#6B3FA0` (purple, the single design exception) | `!` |
| warning | warning | `!` |
| caution | danger | `×` |

Icons are CSS-positioned text glyphs in a circle (no SVG needed).

## Stub docs

```
public_docs/
├─ researcher/
│   ├─ index.md           "Researchers"
│   ├─ index.ru.md        "Исследователи"
│   ├─ first-notebook.md  "Run your first notebook"
│   └─ first-notebook.ru.md "Запустите первый ноутбук"
├─ operator/
│   ├─ index.md           "Lab operators"
│   ├─ index.ru.md        "Операторы лаборатории"
│   ├─ setup-lab-pc.md    "Set up a new lab PC"
│   └─ setup-lab-pc.ru.md "Настройка нового лабораторного ПК"
├─ admin/
│   ├─ index.md           "Server admins"
│   └─ index.ru.md        "Серверные администраторы"
└─ reference/
    ├─ index.md           "Reference"
    └─ index.ru.md        "Справочник"
```

Each file: one H1 (drives sidebar title via `_first_h1`), one paragraph
("This guide is in progress — see [system overview](/docs/system-overview)
for now."). The auto-built nav from `app/nav.py` picks them up; existing
flat `system-overview.md` and `technical-overview.md` continue to render as
top-level entries below the four new section groups.

No moves of existing content in this PR.

## Testing

Three tiers per CLAUDE.md.

### Unit

- **`services/siteapp/tests/test_labs.py`** (new):
  - `aggregate_labs()` with mocked httpx — all-online / mix / all-offline
    fixtures.
  - Malformed JSON / non-200 / timeout → row marked offline.
  - Missing `version` field → online but no `outdated`.
  - `outdated` detection: lt / eq / gt branches.
  - Missing `meta.json` → no `outdated` on any row.
  - `+build_sha` suffix stripped before comparison.
  - Non-PEP-440 version on either side → no `outdated`, doesn't raise.
  - 60s cache: second call within 60s returns cached, after 60s refreshes.
  - Concurrent calls during refresh wait on single lock.
- **`services/siteapp/tests/test_strings.py`** (new):
  - `HOME_STRINGS["en"].keys() == HOME_STRINGS["ru"].keys()`.
  - Same for `DL_STRINGS`.
  - No empty string values.
- **`services/siteapp/tests/test_markdown.py`** (extend):
  - Fenced block ` ```python title="serialhop/cli.py" ` emits
    `<figure class="lb-code"><figcaption>…<span class="lb-code__file">`.
  - Without `title=` → no `.lb-code__file` span.
  - Bleach preserves `figure` / `figcaption` / `button` and their attrs.
  - Custom Pygments style emits expected token classes.
  - Anchor permalinks render with `.lb-anchor` class on H2/H3.
- **`services/siteapp/tests/test_agent.py`** (extend):
  - `_relative_time` covers seconds / minutes / hours / days / weeks
    branches for both EN and RU.

### Service e2e

- **`services/siteapp/tests/e2e/test_home_page.py`** (new):
  - `GET /` returns 200, renders sticky header + headline + status panel +
    topology + quick + getting-started sections.
  - `?lang=ru` flips strings; cookie set.
  - With cookie + no query, RU served.
  - `/api/public/labs` with stubbed roster returns expected shape.
- **`services/siteapp/tests/e2e/test_download_page.py`** (new):
  - `GET /download/agent` with meta.json: renders hero + Windows card with
    CTA + explainer + metadata + 2 coming-soon cards.
  - Without meta.json: disabled CTA, no explainer / metadata, coming-soon
    cards still present.
  - `?lang=ru` flips hero / lede / labels / explainer body.
  - SHA-256 element has `data-copy-text` set.
- **`services/siteapp/tests/e2e/test_docs_page.py`** (extend):
  - Code block with `title="X"` emits `.lb-code__head` with filename.
  - Sidebar `[RU]` pill renders on translated entries only.
  - Breadcrumb + prev/next render on a multi-level doc.
  - 5 admonition flavors render with correct `alert-{kind}` classes.

### Platform integration (bats)

Extend the existing `routes-smoke` cell (or add a `navbar` cell if it
grows):

- New navbar HTML contains brand row + theme toggle markup.
- `data-version` attribute on the injected `<script>` carries deployed
  version.
- Bookmark mode active on `/jupyter/` and `/grafana/`.

Mirror the `compose_images_available` skip pattern per
`test_routes_smoke.bats:11-14`.

## Release strategy

- **Single PR**, single squash-merge. Changes touch `compose/shell/`,
  `compose/Caddyfile.tmpl`, `services/siteapp/`, and `public_docs/` — they
  must land atomically (the templates, tokens, font links, and navbar visual
  rewrite all depend on each other).
- Conventional Commit title: `feat(platform): apply hi-fi UI redesign to
  navbar, Home, Download, and Docs` (the `feat` triggers a minor bump under
  release-please).
- Release-please PR for the resulting version is the integration test gate
  (`pr-platform` runs full bats, `pr-siteapp` runs full e2e, `pr-caddy`
  unchanged but re-validates inject).
- No branch-protection update needed — no new required-check workflow.

## Risks and mitigations

1. **Google Fonts as external dependency.** Slight FOUC if slow, privacy
   footprint. Mitigation: self-host follow-up if it bites.
2. **Lab fan-out latency.** 50 labs × 800 ms timeout = ≤ 1 s wall worst case
   (parallel). 60s cache absorbs sustained load. `httpx` enforces the
   timeout so a hung lab can't stall the response.
3. **`packaging.version.Version` choking on non-PEP-440.** Caught; row gets
   no `outdated` field rather than 5xx.
4. **Russian translations are designer-written.** Native-speaker review is a
   release gate. Spec calls it out; reviewer should sign off explicitly.
5. **Shadow DOM ↔ document theme sync.** One source of truth
   (`localStorage['theme']`), three observers (boot script, native `storage`
   event in other tabs, manual write in originating tab). Tested at unit
   level on the navbar JS module.
6. **Pygments custom style mapping is approximate.** Handoff's intended
   colors don't 1:1 match Pygments token classes. Document the mapping in a
   code comment; ship approximate fidelity.
7. **Stub docs land alongside real docs.** Hierarchy correct, content thin.
   Users following getting-started cards see "this guide is in progress".
   Acceptable for v1 — content is a follow-up.
8. **Breadcrumb / prev-next on flat root entries.** Top-level docs
   (`system-overview`, `technical-overview`) have no parent — helper handles
   `None` parent → renders breadcrumb as just "Docs / Title", prev/next
   siblings within the top-level entry list.
9. **Theme toggle in bookmark mode.** Hidden per design contract. If a user
   theme-toggles inside Jupyter (bookmark mode) and the rail doesn't show a
   toggle, that's correct behavior. Mitigation: tooltip on the persistent
   rail toggle reads "Lab Bridge theme only".

## Out of scope (non-goals)

- Responsive layout below 1280px (handoff says proposed-not-designed; we
  ship desktop-first; narrow viewports are best-effort, not validated).
- Per-user nav customization, persistence beyond theme + sidebar collapse +
  lang.
- Login state / who-is-logged-in indicator.
- Animated transitions beyond the handoff-prescribed timings.
- Search / command palette.
- Custom user-picked accent color (handoff describes `lightenForDark`; not
  v1).
- Per-lab "last seen" timestamp on the status panel (the row layout doesn't
  reserve a slot).
- Re-ordering existing flat docs under the new section folders (kept at
  root; pure content-move PR later).
- Notification of new agent versions to running labs (separate channel —
  `clients.json`'s `agent.version` nudge, not this PR).
- Mobile + touch (bookmark "tap to expand" works as a happy accident; not
  a designed path).
- Linux + Raspberry Pi agent builds. Download page renders static
  coming-soon cards; the actual builds are a separate effort.

## References

- `docs/design_handoff_lab_bridge/README.md` — design handoff
  (visual + content authoritative source).
- `docs/design_handoff_lab_bridge/source/lab-bridge-styles.css` — CSS rules
  to port (skip the `.lb-window` / `.lb-canvas` design-time framing).
- `docs/design_handoff_lab_bridge/source/lab-bridge-{navbar,home,download,docs}.jsx`
  — component structure + copy + interaction reference (not production code
  to lift).
- `docs/superpowers/specs/2026-05-17-shared-navbar-design.md` — navbar
  architecture (already shipped; this spec is the visual layer on top).
- `docs/superpowers/specs/2026-05-16-siteapp-simplification-design.md` —
  current siteapp template structure that this spec edits.
- `docs/superpowers/specs/2026-05-02-md-render-extensions-design.md` —
  current markdown rendering pipeline this spec extends.
- `CLAUDE.md` — invariants: per-service isolation, single VERSION,
  three-tier testing, squash-merge.
