# Docs: in-page TOC + DFS prev/next

**Date:** 2026-05-24
**Status:** Spec
**Scope:** `services/siteapp` — docs rendering only. No changes to `public_docs/` content, no platform / deploy / CI changes.

## Motivation

Two reading-flow gaps in `/docs/`:

1. **No in-page navigation.** Long pages (`architecture/auth.md`, `operator/setup-lab-pc.md`) have no per-page "On this page" outline. Readers must scroll the article to find a heading, or rely on the left sidebar (which only lists pages, not sub-sections).
2. **Prev/Next jumps awkwardly.** Today `prev_next` walks **siblings only** (`services/siteapp/app/docs.py:64-76`). On a section index (e.g. `/docs/researcher/`), "Next" leaves the section entirely instead of entering its first child. On the last child of a section, "Next" is empty and the reader hits a dead-end.

This spec brings the docs rendering in line with the conventions readers know from MkDocs Material: a right-rail per-page outline with scrollspy, and a footer prev/next that walks the whole docs tree in pre-order DFS.

## Decisions

| # | Decision | Choice |
|---|----------|--------|
| Q1 | TOC heading depth | **H2 + H3** (H3s nested under their preceding H2) |
| Q2 | Scrollspy behavior | **Highlight on scroll, update URL hash via `history.replaceState`** |
| Q3 | Narrow-viewport behavior | **Hide TOC below 1280px**, no mobile fallback |
| Q4 | Prev/next scope | **Pure pre-order DFS across the whole tree** |
| Q5 | Prev/next label format | **Distinct eyebrow ("Previous/Next section") when destination is a top-section index; otherwise page title only** |

The Q5 wording differs from the original brainstorming option ("section prefix at boundary"). Under pure pre-order DFS, cross-section transitions always land on the next section's *index page*, so a "Section › Title" prefix degenerates to "Operator › Operator". Using the eyebrow caption to signal the section context avoids the redundancy while still telling the reader "you're about to enter a new section." See [Component 4 — Prev/next label format](#label-formatting) for the exact rule.

## Architecture

Server-side rendering, in keeping with the existing pattern (nav, breadcrumb, prev/next are all server-built in `services/siteapp/app/`). The browser does only one thing: scrollspy.

```
┌──────────────────────────────────────────────────────────────┐
│ docs.py (router)                                             │
│   • build_nav(docs_root)                                     │
│   • build_breadcrumb(nav, current_url)                       │
│   • prev_next(nav, current_url)              ← rewritten     │
│   • _is_top_section(nav, url)                ← new (private) │
│   • render_markdown(text) → Rendered(html, title,            │
│                                       needs_mermaid, toc)    │
│                                              ↑ toc is new    │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ doc.html (template)                                          │
│   <div class="lb-docs-grid">                                 │
│     <article>…breadcrumb, body, prev/next…</article>         │
│     {% if toc %}<nav class="lb-docs-toc">…</nav>{% endif %}  │
│   </div>                                                     │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ docs-toc.js (browser, only when toc is non-empty)            │
│   IntersectionObserver on H2/H3 elements                     │
│     → set data-active on the matching TOC link               │
│     → history.replaceState("#" + anchor)                     │
└──────────────────────────────────────────────────────────────┘
```

## Layout

The docs grid widens from 2 columns (sidebar + content) to 3 columns at desktop (sidebar + article + TOC), folding back to 2 at narrow widths.

### Width budget

| Element | Width | Notes |
|---------|-------|-------|
| Left sidebar (`lb-docs-side`) | 256px fixed | unchanged |
| Article column (`lb-docs-article`) | max 720px, centered | unchanged |
| TOC column (`lb-docs-toc`) | 224px fixed | new; 32px column-gap from article |
| TOC breakpoint | ≥ 1280px viewport | below this, TOC hidden via CSS |

**Why 1280px:** at 1100px viewport, after subtracting sidebar (256), content padding (48 × 2), gap (32), and TOC (224), the article column gets only 492px — too narrow for body text at 14.5px. At 1280px the article gets 672px, comfortably within its 720px cap.

### Grid wrapper

Inside `lb-docs-content`, a new `<div class="lb-docs-grid">` wraps article + TOC:

```css
.lb-docs-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  column-gap: 32px;
}
@media (min-width: 1280px) {
  .lb-docs-grid {
    grid-template-columns: minmax(0, 1fr) 224px;
  }
}
```

Article keeps `max-width: 720px; margin: 0 auto` so it stays centered within its grid cell regardless of whether the TOC column is present. Layout does not shift when TOC is absent (an empty TOC just renders nothing; the grid still has a single column).

### Sticky TOC

```css
.lb-docs-toc {
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
}
@media (max-width: 1279px) {
  .lb-docs-toc { display: none; }
}
```

### Pages with no H2

Server passes `toc=[]`; template skips the `<nav class="lb-docs-toc">` entirely. The grid stays single-column; article remains centered.

## Component 1 — TOC extraction (markdown.py)

### Data model

```python
@dataclass(frozen=True)
class TocEntry:
    level: int                              # 2 or 3
    text: str                               # plain-text heading label
    anchor: str                             # slug, matches anchors_plugin id
    children: tuple["TocEntry", ...] = ()   # H3s nested under their H2
```

`Rendered` gains a `toc: list[TocEntry]` field (default `[]`), reusing the existing token walk in `render_markdown`.

### Extraction

New function `_extract_toc(tokens) -> list[TocEntry]`:

1. Single linear scan of the token stream.
2. For each `heading_open` with `tag in {"h2", "h3"}`:
   - Use the next `inline` token; reuse the existing `_inline_text(token)` helper for the plain-text label.
   - Compute the slug via the existing `_slug(text)` helper.
   - Track slug counts in a `dict[str, int]` so duplicates get the `-2`, `-3` suffix the anchors plugin uses for collisions. This guarantees TOC anchors match body IDs even when authors repeat heading text.
   - Skip entries where the plain-text label is empty after `_inline_text` (defensive — markdown-it shouldn't emit these).
3. Second pass nests H3s under the preceding H2; H3s that appear before any H2 become top-level entries (rare but allowed).

### Why server-side

- The token walk already happens for `_title_from_tokens`, `_apply_alerts`, `_has_mermaid`. Adding TOC extraction shares the pass.
- Slug logic stays in one place. Anchor IDs (`anchors_plugin` slug) and TOC links (`_slug` call) cannot drift apart.
- No FOUC, no flash of unstyled content; the right rail is present on first paint.
- Matches the existing pattern — server builds every other navigational artifact (sidebar, breadcrumb, prev/next).

## Component 2 — Template (doc.html)

```html
<div class="lb-docs-grid">
  <article class="lb-docs-article">
    {# breadcrumb, body, prev/next — unchanged structure #}
  </article>

  {% if toc %}
  <nav class="lb-docs-toc" aria-label="On this page">
    <div class="lb-docs-toc__title">{{ s.toc_title }}</div>
    <ul class="lb-docs-toc__list">
      {% for h in toc %}
        <li>
          <a class="lb-docs-toc__link"
             href="#{{ h.anchor }}"
             data-toc-anchor="{{ h.anchor }}"
             data-level="2">{{ h.text }}</a>
          {% if h.children %}
            <ul>
              {% for sub in h.children %}
                <li><a class="lb-docs-toc__link"
                       href="#{{ sub.anchor }}"
                       data-toc-anchor="{{ sub.anchor }}"
                       data-level="3">{{ sub.text }}</a></li>
              {% endfor %}
            </ul>
          {% endif %}
        </li>
      {% endfor %}
    </ul>
  </nav>
  {% endif %}
</div>
```

**Source order:** article first, TOC second. Screen readers and `view-source` see content before nav. CSS grid handles the visual placement (TOC on the right at desktop).

**Bleach allow-list:** the TOC `<nav>` lives outside `lb-docs-article__body` (which is the only sanitized region). No allow-list change needed; TOC HTML is template-generated.

**JS gating:** `<script src="/_static/docs-toc.js" defer>` loads only when `toc` is non-empty. The existing `docs-sidebar.js` is unaffected.

## Component 3 — Scrollspy (docs-toc.js)

≈40 lines vanilla JS, defer-loaded. No external dependencies.

```text
on DOMContentLoaded:
  links = querySelectorAll('[data-toc-anchor]')
  headings = links.map(l => document.getElementById(l.dataset.tocAnchor))
                   .filter(Boolean)

  active = new Set()
  observer = new IntersectionObserver(entries => {
    for (e of entries) {
      if (e.isIntersecting) active.add(e.target.id)
      else                  active.delete(e.target.id)
    }
    // pick the topmost active heading in document order
    topId = headings.map(h => h.id).find(id => active.has(id))
    setActive(topId)
  }, { rootMargin: "0px 0px -75% 0px" })

  headings.forEach(h => observer.observe(h))

  function setActive(id):
    if (id === currentActive) return
    currentActive = id
    links.forEach(l => l.toggleAttribute('data-active',
                                        l.dataset.tocAnchor === id))
    if (id) history.replaceState(null, "", "#" + id)
```

**`rootMargin: "0px 0px -75% 0px"`** — heading becomes active once it crosses into the top 25% of the viewport. Empirically the most natural-feeling threshold; matches MkDocs Material.

**`history.replaceState` (not `pushState`)** — URL hash updates silently; no history-stack pollution, no scroll jump.

**Defensive:** `if (window.__docsTocLoaded) return;` guard mirrors `docs-sidebar.js`.

## Component 4 — DFS prev/next (nav.py + docs.py)

### New helper in nav.py

```python
def flatten_nav(nav: list[NavEntry]) -> list[NavEntry]:
    """Pre-order DFS — every NavEntry in reading order."""
    out: list[NavEntry] = []
    def walk(entries: list[NavEntry]) -> None:
        for e in entries:
            out.append(e)
            if e.children:
                walk(list(e.children))
    walk(nav)
    return out
```

(`_is_top_section` lives in `docs.py` because it's only used by the route's label-formatting logic.)

### Rewritten prev_next in docs.py

```python
def prev_next(nav, current_url):
    flat = flatten_nav(nav)
    for i, e in enumerate(flat):
        if e.url == current_url:
            prev = flat[i - 1] if i > 0 else None
            nxt = flat[i + 1] if i + 1 < len(flat) else None
            return prev, nxt
    return None, None
```

The old sibling-walking `_find_siblings` is deleted (dead code).

### Label formatting

The rule: the **eyebrow caption** signals whether the destination is a top section (a new chapter) or an in-section page. The **title** is always just the destination's own title.

| Destination | Eyebrow | Title |
|-------------|---------|-------|
| Top-section index (depth-0 in nav) | "Previous section" / "Next section" | section title |
| Any other entry | "Previous" / "Next" | page title |

This avoids the redundant "Operator › Operator" label that a `Section › Title` prefix would produce under pre-order DFS, while still telling the reader they're crossing into a new section.

`docs_path` computes booleans and passes them to the template:

```python
def _is_top_section(nav: list[NavEntry], url: str) -> bool:
    return any(top.url == url for top in nav)

prev, nxt = prev_next(nav, current_url)
prev_is_section = bool(prev) and _is_top_section(nav, prev.url)
next_is_section = bool(nxt)  and _is_top_section(nav, nxt.url)
```

Template (in `lb-docs-article__prevnext` footer):

```html
{% if prev %}
  <a class="lb-docs-article__prev" href="{{ prev.url }}">
    <span class="lb-docs-article__nav-eyebrow">
      &larr; {% if prev_is_section %}Previous section{% else %}Previous{% endif %}
    </span>
    <span class="lb-docs-article__nav-title">{{ prev.title_en }}</span>
  </a>
{% endif %}
```

(Real template uses the language-aware title lookup already used elsewhere; shown above with `title_en` for brevity. Russian eyebrow strings — "Предыдущий раздел" / "Следующий раздел" / "Назад" / "Далее" — live in `app/strings.py`.)

**Why `_is_top_section` over `top_section_of`:** the label rule only needs a boolean "is this destination a top-level entry?" — we never need the ancestor itself. Keeping the helper minimal avoids over-engineering for the deeper-tree case (top sections having sub-sections having pages) which the docs don't currently use.

### Edge cases

- **Home (`/docs/`, depth-0 leaf):** `_is_top_section` returns True (Home appears in `nav` at depth-0). So Home's eyebrow is "Previous/Next section" when navigated to. Acceptable — Home is conceptually a top-level entry.
- **Childless top sections (e.g., Overview):** depth-0 in `nav`, so `_is_top_section` is True. Eyebrow says "Next section: Overview" — correct.
- **In-section navigation:** child page → child page, both have `_is_top_section` false → eyebrows say plain "Previous"/"Next".
- **Russian eyebrow strings:** new `DOCS_STRINGS: dict[Lang, dict[str, str]]` block in `app/strings.py` (following the existing `HOME_STRINGS` / `DL_STRINGS` pattern), with keys `prev`, `next`, `prev_section`, `next_section`, `toc_title`. `docs.py` passes `s=DOCS_STRINGS[chosen]` to the template; the template uses `{{ s.prev_section }}` etc.
- **Single-page docs (only Home in nav):** prev = next = None for Home. Footer renders nothing (today's `{% if prev or next %}` guard already handles this).

## Testing

### Unit tests — `tests/test_nav.py`

Additions:
- `test_flatten_nav_pre_order_dfs` — exact reading order on the sample tree (matches the expected pre-order walk).
- `test_flatten_nav_includes_home_first` — Home at position 0 when root has `index.md`.
- `test_flatten_nav_visits_section_before_children` — section index immediately precedes its first child.

Replacements (existing tests change to new semantics):
- `test_prev_next_section_index_to_first_child` — on `/docs/researcher/`, next is the first researcher child.
- `test_prev_next_last_child_to_next_top_section` — on the last researcher child, next is the operator section index.
- `test_prev_next_home_has_no_prev` — Home → prev is None.
- `test_prev_next_last_overall_has_no_next` — the last entry in DFS order → next is None.

### Unit tests — `tests/test_markdown.py`

New (module-level, no fixture required):
- `test_toc_extracts_h2_and_h3_only` — H1 excluded, H4 excluded.
- `test_toc_h3_nested_under_preceding_h2` — H3 attaches to the most-recent H2 as a child.
- `test_toc_h3_before_any_h2_is_top_level`.
- `test_toc_anchor_matches_anchors_plugin_slug` — render the same markdown; parse rendered HTML for `<h2 id="...">` / `<h3 id="...">`; assert TOC anchors equal the in-order list of body IDs.
- `test_toc_duplicate_headings_get_suffixed_anchors` — two identical H2s → anchors `dupe` and `dupe-2`.
- `test_toc_empty_when_no_h2_or_h3` — single-H1 page → empty list.

### Route tests — `tests/test_routes_docs.py`

- `test_toc_renders_when_page_has_h2` — response contains `class="lb-docs-toc"` and `href="#some-heading"`.
- `test_toc_omitted_when_page_has_no_h2` — `lb-docs-toc` absent.
- `test_prevnext_eyebrow_says_next_for_in_section_page` — next entry is a child page → eyebrow text is "Next" (and "Previous" for prev).
- `test_prevnext_eyebrow_says_next_section_for_top_section_destination` — next entry is a top-section index → eyebrow text is "Next section".
- `test_prevnext_eyebrow_uses_russian_strings_when_lang_ru` — Russian eyebrow text appears when `?lang=ru`.
- `test_prevnext_omitted_on_single_entry_nav` — when prev = next = None, the footer doesn't render.

### Out of scope

- **No bats / no service-e2e changes.** Siteapp's `tests/e2e/` tier exists, but TOC rendering and prev/next ordering are well-covered by unit + route tests against `TestClient`. Adding a Playwright cell or a bats file for a docs render change is over-spec.
- **No automated test of scrollspy.** Siteapp has no JS test runner; standing one up for ~40 lines of vanilla JS is YAGNI. Manual verification on `task dev` covers it (scroll a long page like `architecture/auth.md`; confirm TOC highlight tracks visible H2; URL hash updates with no scroll jump).

## File touch list

```
services/siteapp/app/markdown.py            # +TocEntry, +_extract_toc, +toc on Rendered
services/siteapp/app/nav.py                 # +flatten_nav
services/siteapp/app/docs.py                # rewrite prev_next using flatten_nav,
                                            #   add _is_top_section, pass toc + s
                                            #   (DOCS_STRINGS) + *_is_section into
                                            #   template context; delete _find_siblings
services/siteapp/app/strings.py             # +DOCS_STRINGS (en/ru): prev, next,
                                            #   prev_section, next_section, toc_title
services/siteapp/app/templates/doc.html     # wrap article in .lb-docs-grid,
                                            #   render TOC nav, update prev/next eyebrow,
                                            #   defer-load docs-toc.js when toc non-empty
services/siteapp/app/static/site.css        # .lb-docs-grid, .lb-docs-toc*, breakpoint
services/siteapp/app/static/docs-toc.js     # NEW — scrollspy
services/siteapp/tests/test_nav.py          # flatten_nav + new prev/next semantics
services/siteapp/tests/test_markdown.py     # TOC extraction tests
services/siteapp/tests/test_routes_docs.py  # TOC rendering + prev/next eyebrow tests
```

No changes to `public_docs/`, `_nav.yaml`, deploy scripts, compose templates, or CI workflows.

## Non-goals

- Mobile "On this page" disclosure block (Q3 left open for future work).
- Configurable TOC depth per page (e.g., front-matter override).
- TOC for the auto-generated section index pages (those just inherit whatever their `index.md` declares).
- A general "next chapter" / "previous chapter" concept distinct from DFS prev/next.
- Any change to anchor IDs, sidebar tree shape, breadcrumb, language switcher.

## Risk & rollout

- **Risk:** anchor/TOC drift. Mitigated by `test_toc_anchor_matches_anchors_plugin_slug` (asserts TOC links match rendered body IDs by parsing rendered HTML, not by computing the slug a second time in test).
- **Risk:** layout regression on narrow viewports. Mitigated by keeping the article column behavior identical when TOC is absent (single-column grid centers the article exactly as today's flex layout does).
- **Risk:** scrollspy churning the URL bar. Mitigated by `replaceState` (no history entries) and the deliberate 75% rootMargin (only one heading active at a time, transitions are slow as the user scrolls).
- **Rollout:** ships in a single PR via the standard `pr-siteapp` workflow. No coordinated release-please bump beyond the normal feat commit.
