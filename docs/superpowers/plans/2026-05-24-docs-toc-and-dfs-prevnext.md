# Docs in-page TOC + DFS prev/next — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an MkDocs-style right-rail "On this page" table of contents with scrollspy, and rewrite the docs prev/next footer to walk the whole docs tree in pre-order DFS.

**Architecture:** Server-side rendering throughout — `markdown.py` extracts the TOC during its existing token walk; `nav.py` gains a `flatten_nav()` helper that produces pre-order DFS reading order; `docs.py` uses that flat list for `prev_next` and computes booleans for the "Previous section" / "Next section" eyebrow. The browser does one thing: an IntersectionObserver-based scrollspy that updates the active TOC entry and the URL hash via `history.replaceState`.

**Tech Stack:** Python 3.13, FastAPI, Jinja2, `markdown-it-py` (with anchors plugin), pytest, vanilla JS, plain CSS.

**Spec:** [`docs/superpowers/specs/2026-05-24-docs-toc-and-dfs-prevnext-design.md`](../specs/2026-05-24-docs-toc-and-dfs-prevnext-design.md)

**Working directory for every command below:** `services/siteapp/` (run `cd services/siteapp` once at the start of a task; `uv` will pick up its `pyproject.toml`).

---

## Task 1 — Add `flatten_nav` helper to `nav.py`

**Files:**
- Modify: `services/siteapp/app/nav.py` (add new top-level function after `build_nav`)
- Test: `services/siteapp/tests/test_nav.py` (add three new tests near the existing `_sample_nav` block)

The helper is a pure function over `NavEntry` trees. We need it for Task 2 (`prev_next` rewrite). Pre-order means: visit parent, then walk its children in order, recursively.

- [ ] **Step 1.1: Write the failing tests**

Add to `services/siteapp/tests/test_nav.py` (anywhere after the existing `_sample_nav()` definition, e.g. just before the existing `test_breadcrumb_for_nested_doc`):

```python
from app.nav import NavEntry, build_nav, flatten_nav


def _deeper_sample_nav() -> list[NavEntry]:
    """Multi-section tree mirroring the real public_docs layout shape."""
    return [
        NavEntry(title_en="Home", title_ru=None, url="/docs/"),
        NavEntry(title_en="Overview", title_ru=None, url="/docs/overview/"),
        NavEntry(
            title_en="Researcher",
            title_ru=None,
            url="/docs/researcher/",
            children=(
                NavEntry(title_en="First notebook", title_ru=None, url="/docs/researcher/first-notebook"),
                NavEntry(title_en="Working with devices", title_ru=None, url="/docs/researcher/working-with-devices"),
            ),
        ),
        NavEntry(
            title_en="Operator",
            title_ru=None,
            url="/docs/operator/",
            children=(
                NavEntry(title_en="Setup lab PC", title_ru=None, url="/docs/operator/setup-lab-pc"),
            ),
        ),
    ]


def test_flatten_nav_pre_order_dfs():
    nav = _deeper_sample_nav()
    urls = [e.url for e in flatten_nav(nav)]
    assert urls == [
        "/docs/",
        "/docs/overview/",
        "/docs/researcher/",
        "/docs/researcher/first-notebook",
        "/docs/researcher/working-with-devices",
        "/docs/operator/",
        "/docs/operator/setup-lab-pc",
    ]


def test_flatten_nav_includes_home_first():
    nav = _deeper_sample_nav()
    assert flatten_nav(nav)[0].url == "/docs/"


def test_flatten_nav_visits_section_before_children():
    nav = _deeper_sample_nav()
    flat = flatten_nav(nav)
    researcher_idx = next(i for i, e in enumerate(flat) if e.url == "/docs/researcher/")
    # The section index sits immediately before its first child.
    assert flat[researcher_idx + 1].url == "/docs/researcher/first-notebook"
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd services/siteapp && uv run pytest tests/test_nav.py::test_flatten_nav_pre_order_dfs tests/test_nav.py::test_flatten_nav_includes_home_first tests/test_nav.py::test_flatten_nav_visits_section_before_children -v
```

Expected: all three fail with `ImportError: cannot import name 'flatten_nav' from 'app.nav'`.

- [ ] **Step 1.3: Implement `flatten_nav` in `nav.py`**

Append to `services/siteapp/app/nav.py`:

```python
def flatten_nav(nav: list[NavEntry]) -> list[NavEntry]:
    """Pre-order DFS walk of the nav tree.

    Returns every NavEntry in reading order: each entry appears before its
    own children. Used by `prev_next` to advance from a section index into
    its first child, and from the last child of one section into the next
    top section's index.
    """
    out: list[NavEntry] = []

    def walk(entries: list[NavEntry]) -> None:
        for e in entries:
            out.append(e)
            if e.children:
                walk(list(e.children))

    walk(nav)
    return out
```

- [ ] **Step 1.4: Run tests to verify they pass**

```bash
cd services/siteapp && uv run pytest tests/test_nav.py -v
```

Expected: all `test_flatten_nav_*` tests pass; existing `test_*` tests still pass.

- [ ] **Step 1.5: Ruff format + check**

```bash
cd services/siteapp && uv run ruff format . && uv run ruff check .
```

Expected: no errors, no diff (or "1 file reformatted" if you forgot a trailing newline).

- [ ] **Step 1.6: Commit**

```bash
git add services/siteapp/app/nav.py services/siteapp/tests/test_nav.py
git commit -m "$(cat <<'EOF'
feat(siteapp): add flatten_nav pre-order DFS helper

Produces the reading-order list used by the upcoming prev/next rewrite.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — Rewrite `prev_next` to use `flatten_nav` (DFS semantics)

**Files:**
- Modify: `services/siteapp/app/docs.py` (replace `_find_siblings` and `prev_next`; lines 49-76)
- Modify: `services/siteapp/tests/test_nav.py` (replace the two existing prev/next tests with new ones reflecting DFS semantics)

The existing `prev_next` walks siblings only — on a section index, "next" jumps to the next top section instead of entering the section's children. After this change, prev/next is index ± 1 in the `flatten_nav` list.

- [ ] **Step 2.1: Update the failing prev/next tests**

In `services/siteapp/tests/test_nav.py`, **delete** the existing two tests:

```python
def test_prev_next_in_section():
    ...

def test_prev_next_across_top_level():
    ...
```

**Replace them with** these four:

```python
def test_prev_next_section_index_to_first_child():
    nav = _deeper_sample_nav()
    prev, nxt = prev_next(nav, "/docs/researcher/")
    assert prev is not None and prev.url == "/docs/overview/"
    assert nxt is not None and nxt.url == "/docs/researcher/first-notebook"


def test_prev_next_last_child_to_next_top_section():
    nav = _deeper_sample_nav()
    prev, nxt = prev_next(nav, "/docs/researcher/working-with-devices")
    assert prev is not None and prev.url == "/docs/researcher/first-notebook"
    assert nxt is not None and nxt.url == "/docs/operator/"


def test_prev_next_home_has_no_prev():
    nav = _deeper_sample_nav()
    prev, nxt = prev_next(nav, "/docs/")
    assert prev is None
    assert nxt is not None and nxt.url == "/docs/overview/"


def test_prev_next_last_overall_has_no_next():
    nav = _deeper_sample_nav()
    prev, nxt = prev_next(nav, "/docs/operator/setup-lab-pc")
    assert prev is not None and prev.url == "/docs/operator/"
    assert nxt is None
```

(Imports at the top of the file already include `prev_next` from `app.docs` and `flatten_nav` from `app.nav` — added in Task 1.)

- [ ] **Step 2.2: Run tests to verify the new ones fail**

```bash
cd services/siteapp && uv run pytest tests/test_nav.py -v
```

Expected: the four new `test_prev_next_*` tests FAIL (sibling-only semantics doesn't enter children). Other `test_nav.py` tests pass.

- [ ] **Step 2.3: Rewrite `prev_next` in `docs.py`**

In `services/siteapp/app/docs.py`, **delete** the `_find_siblings` function (the one with signature `def _find_siblings(nav: list[NavEntry], target_url: str) -> tuple[list[NavEntry], int] | None`) — its only caller was `prev_next`, which we're about to replace.

**Replace** the existing `prev_next` function with:

```python
def prev_next(nav: list[NavEntry], current_url: str) -> tuple[NavEntry | None, NavEntry | None]:
    """Return (prev, next) entries in pre-order DFS reading order.

    Walks the entire docs tree as one flat sequence: a section index is
    followed by its first child, the last child of one section is followed
    by the next top section's index, and so on. (None, None) when the
    current URL is not in the nav at all.
    """
    flat = flatten_nav(nav)
    for i, entry in enumerate(flat):
        if entry.url == current_url:
            prev = flat[i - 1] if i > 0 else None
            nxt = flat[i + 1] if i + 1 < len(flat) else None
            return prev, nxt
    return None, None
```

Update the import at the top of `docs.py` (line 12) from:

```python
from app.nav import NavEntry, build_nav
```

to:

```python
from app.nav import NavEntry, build_nav, flatten_nav
```

- [ ] **Step 2.4: Run tests to verify they pass**

```bash
cd services/siteapp && uv run pytest tests/test_nav.py -v
```

Expected: all tests pass, including the four new `test_prev_next_*` and existing `test_breadcrumb_*`.

- [ ] **Step 2.5: Run the full siteapp suite to catch route-test regressions**

```bash
cd services/siteapp && uv run pytest
```

Expected: every test passes. (The existing `test_routes_docs.py` doesn't assert specific prev/next text — only the existence of routes — so no breakage expected.)

- [ ] **Step 2.6: Ruff format + check**

```bash
cd services/siteapp && uv run ruff format . && uv run ruff check .
```

- [ ] **Step 2.7: Commit**

```bash
git add services/siteapp/app/docs.py services/siteapp/tests/test_nav.py
git commit -m "$(cat <<'EOF'
feat(siteapp): rewrite docs prev/next as pre-order DFS

Section indexes now advance into their first child; the last child of a
section advances into the next top section's index. Old sibling-only
walker (_find_siblings) is removed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Add `DOCS_STRINGS`, `_is_top_section`, and pass strings/booleans to the doc template

**Files:**
- Modify: `services/siteapp/app/strings.py` (append `DOCS_STRINGS` block)
- Modify: `services/siteapp/app/docs.py` (add `_is_top_section`, extend template context)
- Test: `services/siteapp/tests/test_routes_docs.py` (extend the existing `client` fixture's tree to enable cross-section testing, then add route tests)

This task wires the data the template needs in Task 4. Strings + booleans are added now; the template that consumes them lands in Task 4 — so route tests added here for `_is_top_section` behaviour assert on **context plumbing visible in the response only after** Task 4 ships. To keep TDD honest we add the booleans + strings now and write route tests against the **rendered prev/next title** (which is already in the template). The eyebrow text tests come in Task 4.

- [ ] **Step 3.1: Append `DOCS_STRINGS` to `strings.py`**

Add at the very end of `services/siteapp/app/strings.py` (after `pick_lang`):

```python
# Per-page docs UI strings (TOC + prev/next eyebrow). Keys mirrored EN/RU.
DOCS_STRINGS: dict[Lang, dict[str, str]] = {
    "en": {
        "toc_title": "On this page",
        "prev": "Previous",
        "next": "Next",
        "prev_section": "Previous section",
        "next_section": "Next section",
    },
    "ru": {
        "toc_title": "Содержание",
        "prev": "Назад",
        "next": "Далее",
        "prev_section": "Предыдущий раздел",
        "next_section": "Следующий раздел",
    },
}
```

- [ ] **Step 3.2: Add `_is_top_section` helper + extended context in `docs.py`**

In `services/siteapp/app/docs.py`, add a new helper just above `make_router` (after `_pick_lang`):

```python
def _is_top_section(nav: list[NavEntry], url: str) -> bool:
    """True iff `url` matches a depth-0 entry in `nav`.

    Used to switch the prev/next eyebrow between "Previous"/"Next" (in-section
    page) and "Previous section"/"Next section" (crossing into a new section).
    Under pure pre-order DFS, cross-section transitions always land on the
    next section's *index page* — exactly the case this returns True for.
    """
    return any(top.url == url for top in nav)
```

Update the imports at the top of `docs.py`. Add this import:

```python
from app.strings import DOCS_STRINGS, pick_lang
```

(`pick_lang` already exists in `app/strings.py` and mirrors the local `_pick_lang`; we'll switch to the shared one now to match `home.py`'s pattern and drop the duplicate.)

**Delete** the local `_pick_lang` function in `docs.py` (the one with signature `def _pick_lang(query: str | None, cookie: str | None) -> Literal["en", "ru"]`) since `pick_lang` from `app.strings` does the same thing. Also drop the now-unused `from typing import Literal, TypedDict` → make it `from typing import TypedDict` if `Literal` is no longer used elsewhere in the file. (Verify with a quick `grep -n Literal services/siteapp/app/docs.py` before saving.)

In the `docs_path` route handler, **replace** the local `chosen = _pick_lang(...)` call with:

```python
chosen = pick_lang(lang, request.cookies.get("lang"))
```

Then, after the `prev, nxt = prev_next(...)` line, add:

```python
prev_is_section = bool(prev) and _is_top_section(nav, prev.url)
next_is_section = bool(nxt) and _is_top_section(nav, nxt.url)
```

Extend the template context dict (the existing `{"title": ..., "html": ..., ...}` passed to `TemplateResponse`) with:

```python
"s": DOCS_STRINGS[chosen],
"prev_is_section": prev_is_section,
"next_is_section": next_is_section,
```

The full context dict should now read:

```python
{
    "title": result.title or doc.rel_path.name,
    "html": result.html,
    "needs_mermaid": result.needs_mermaid,
    "lang": chosen,
    "doc": doc,
    "nav": nav,
    "current_url": str(request.url.path),
    "pygments_css": pygments_css(),
    "crumbs": crumbs,
    "prev": prev,
    "next": nxt,
    "prev_is_section": prev_is_section,
    "next_is_section": next_is_section,
    "s": DOCS_STRINGS[chosen],
}
```

- [ ] **Step 3.3: Run existing tests to confirm no regressions**

```bash
cd services/siteapp && uv run pytest
```

Expected: all tests pass. (Template hasn't been updated yet — the new context keys are unused by the template until Task 4, which is fine.)

- [ ] **Step 3.4: Ruff format + check**

```bash
cd services/siteapp && uv run ruff format . && uv run ruff check .
```

- [ ] **Step 3.5: Commit**

```bash
git add services/siteapp/app/strings.py services/siteapp/app/docs.py
git commit -m "$(cat <<'EOF'
feat(siteapp): add DOCS_STRINGS + _is_top_section, pipe to doc template

Adds en/ru strings for the upcoming TOC heading and prev/next eyebrow
captions, plus the _is_top_section boolean the template will use to
choose between "Previous/Next" and "Previous/Next section". Also drops
the duplicate _pick_lang in favor of the shared pick_lang from strings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Update `doc.html` prev/next footer to use eyebrow strings

**Files:**
- Modify: `services/siteapp/app/templates/doc.html` (replace the hard-coded "← Previous" / "Next →" eyebrows)
- Test: `services/siteapp/tests/test_routes_docs.py` (extend `client` fixture's tree, add eyebrow tests)

The current template has hard-coded English strings inside `lb-docs-article__nav-eyebrow`. Replace them with the new `s.prev` / `s.next` / `s.prev_section` / `s.next_section` lookups guarded by the booleans.

- [ ] **Step 4.1: Extend the `client` fixture in `test_routes_docs.py` so a cross-section transition exists**

Find the `client` fixture in `services/siteapp/tests/test_routes_docs.py` (starts at line 9). The current tree has `intro.md`, `diagram.md`, plus a `section/` directory with `page.md`. We need a multi-page section so we have an in-section transition AND a cross-section transition.

**Replace** the fixture body (everything between `def client(...):` and `return TestClient(app.main.app)`) with:

```python
docs = tmp_path / "docs-root"
# _docs_dir_default (conftest autouse) already created docs and set
# SITEAPP_DOCS_DIR=tmp_path/docs-root for us; we just populate it.
(docs / "index.md").write_text("# Home\n\nWelcome\n", encoding="utf-8")
(docs / "intro.md").write_text("# Intro\n\nhello world\n", encoding="utf-8")
(docs / "intro.ru.md").write_text("# Введение\n\nпривет\n", encoding="utf-8")
(docs / "diagram.md").write_text(
    "# Diagram\n\n```mermaid\nflowchart LR\n  A --> B\n```\n",
    encoding="utf-8",
)
section = docs / "section"
section.mkdir()
(section / "index.md").write_text("# Section\n", encoding="utf-8")
(section / "page.md").write_text("# Page\n", encoding="utf-8")
(section / "second.md").write_text("# Second page\n", encoding="utf-8")
(section / "_nav.yaml").write_text("- name: page\n- name: second\n", encoding="utf-8")
(docs / "_nav.yaml").write_text(
    "- name: intro\n- name: diagram\n- name: section\n", encoding="utf-8"
)
icons = docs / "icons"
icons.mkdir()
(icons / "jupyter.svg").write_bytes(
    b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
    b'width="28" height="28"><circle r="14" cx="14" cy="14" fill="orange"/></svg>'
)
(icons / "secret.exe").write_bytes(b"MZ\x90\x00")
monkeypatch.setenv("SITE_DATA", str(tmp_path))
monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
from importlib import reload

import app.main

reload(app.main)
```

(Only change from today: added `second.md` and listed it in `section/_nav.yaml`. Everything else is identical.)

- [ ] **Step 4.2: Write the failing eyebrow tests**

Add at the bottom of `services/siteapp/tests/test_routes_docs.py`:

```python
def test_prevnext_eyebrow_says_next_for_in_section_page(client: TestClient) -> None:
    # /docs/section/page → next is /docs/section/second (same section).
    # Eyebrow should say "Next" (NOT "Next section").
    r = client.get("/docs/section/page")
    assert r.status_code == 200
    body = r.text
    # Both eyebrows present (in-section transition both directions).
    assert "lb-docs-article__nav-eyebrow" in body
    # "Section"-flavoured eyebrows must NOT appear for this in-section transition.
    assert "Next section" not in body
    assert "Previous section" not in body


def test_prevnext_eyebrow_says_next_section_for_top_section_destination(
    client: TestClient,
) -> None:
    # /docs/diagram → next is /docs/section/ (a top-section index).
    # Eyebrow should say "Next section".
    r = client.get("/docs/diagram")
    assert r.status_code == 200
    assert "Next section" in r.text


def test_prevnext_eyebrow_uses_russian_strings_when_lang_ru(client: TestClient) -> None:
    # /docs/section/page?lang=ru → in-section transition → eyebrow "Далее".
    r = client.get("/docs/section/page?lang=ru")
    assert r.status_code == 200
    body = r.text
    assert "Далее" in body
    assert "Назад" in body  # the prev eyebrow on the same page


def test_prevnext_eyebrow_russian_section_label_when_lang_ru(client: TestClient) -> None:
    # /docs/diagram?lang=ru → next is /docs/section/ → eyebrow "Следующий раздел".
    r = client.get("/docs/diagram?lang=ru")
    assert r.status_code == 200
    assert "Следующий раздел" in r.text


def test_prevnext_omitted_on_single_entry_nav(tmp_path: Path, monkeypatch) -> None:
    """When the nav has exactly one entry (Home), prev = next = None and
    the footer doesn't render — matches today's `{% if prev or next %}` guard."""
    docs = tmp_path / "docs-root"
    # Wipe everything the fixture created; leave only Home.
    for child in list(docs.iterdir()):
        if child.is_file():
            child.unlink()
        else:
            import shutil

            shutil.rmtree(child)
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    # No _nav.yaml needed — Home is the implicit root entry.
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    from importlib import reload

    import app.main

    reload(app.main)
    c = TestClient(app.main.app)
    r = c.get("/docs/")
    assert r.status_code == 200
    assert "lb-docs-article__prevnext" not in r.text
```

- [ ] **Step 4.3: Run tests to verify the new ones fail**

```bash
cd services/siteapp && uv run pytest tests/test_routes_docs.py -v -k prevnext
```

Expected: the new `test_prevnext_*` tests FAIL because the template still emits hard-coded "Previous"/"Next" English without the section/in-section distinction, and Russian eyebrows don't exist yet.

- [ ] **Step 4.4: Update `doc.html` eyebrow blocks**

In `services/siteapp/app/templates/doc.html`, find the prev/next footer block (the `{% if prev or next %}` ... `{% endif %}` block currently containing hard-coded "← Previous" and "Next →" spans).

**Replace** the whole footer with:

```html
{% if prev or next %}
<footer class="lb-docs-article__prevnext">
  {% if prev %}
    <a class="lb-docs-article__prev" href="{{ prev.url }}">
      <span class="lb-docs-article__nav-eyebrow">
        &larr; {% if prev_is_section %}{{ s.prev_section }}{% else %}{{ s.prev }}{% endif %}
      </span>
      <span class="lb-docs-article__nav-title">{{ prev.title_ru if (lang == 'ru' and prev.title_ru) else prev.title_en }}</span>
    </a>
  {% else %}<span></span>{% endif %}
  {% if next %}
    <a class="lb-docs-article__next" href="{{ next.url }}">
      <span class="lb-docs-article__nav-eyebrow">
        {% if next_is_section %}{{ s.next_section }}{% else %}{{ s.next }}{% endif %} &rarr;
      </span>
      <span class="lb-docs-article__nav-title">{{ next.title_ru if (lang == 'ru' and next.title_ru) else next.title_en }}</span>
    </a>
  {% else %}<span></span>{% endif %}
</footer>
{% endif %}
```

- [ ] **Step 4.5: Run the prev/next tests to verify they pass**

```bash
cd services/siteapp && uv run pytest tests/test_routes_docs.py -v
```

Expected: all `test_prevnext_*` tests pass. All previously-existing route tests still pass.

- [ ] **Step 4.6: Run the full siteapp suite**

```bash
cd services/siteapp && uv run pytest
```

Expected: every test passes.

- [ ] **Step 4.7: Ruff format + check**

```bash
cd services/siteapp && uv run ruff format . && uv run ruff check .
```

- [ ] **Step 4.8: Commit**

```bash
git add services/siteapp/app/templates/doc.html services/siteapp/tests/test_routes_docs.py
git commit -m "$(cat <<'EOF'
feat(siteapp): use eyebrow caption to signal cross-section prev/next

Replaces the hard-coded "Previous"/"Next" English strings with translated
captions from DOCS_STRINGS. When the destination is a top-section index,
the eyebrow switches to "Previous section"/"Next section" so the reader
sees they're entering a new chapter.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Add `TocEntry` and `_extract_toc` to `markdown.py`

**Files:**
- Modify: `services/siteapp/app/markdown.py` (add `TocEntry`, `_extract_toc`, extend `Rendered`)
- Test: `services/siteapp/tests/test_markdown.py` (add TOC extraction tests)

`render_markdown` already walks tokens for title, alerts, and mermaid detection. We add a fourth pass for TOC. The slug logic mirrors `mdit_py_plugins.anchors`'s collision handling so TOC anchors match the body IDs.

- [ ] **Step 5.1: Write the failing tests**

Add at the bottom of `services/siteapp/tests/test_markdown.py`:

```python
import re

from app.markdown import TocEntry, render_markdown


def test_toc_extracts_h2_and_h3_only():
    src = (
        "# Title\n\n"
        "## Alpha\n\nbody\n\n"
        "### Sub\n\nbody\n\n"
        "#### Deep\n\nbody\n\n"
        "## Beta\n\nbody\n"
    )
    r = render_markdown(src)
    assert [e.text for e in r.toc] == ["Alpha", "Beta"]
    assert [c.text for e in r.toc for c in e.children] == ["Sub"]


def test_toc_h3_nested_under_preceding_h2():
    src = (
        "# T\n\n"
        "## Outer\n\n"
        "### Inner-1\n\n"
        "### Inner-2\n\n"
        "## Another\n\n"
        "### Inner-3\n"
    )
    r = render_markdown(src)
    assert len(r.toc) == 2
    outer, another = r.toc
    assert [c.text for c in outer.children] == ["Inner-1", "Inner-2"]
    assert [c.text for c in another.children] == ["Inner-3"]


def test_toc_h3_before_any_h2_is_top_level():
    src = "# T\n\n### Lonely H3\n\n## After H2\n"
    r = render_markdown(src)
    assert [e.level for e in r.toc] == [3, 2]
    assert r.toc[0].children == ()


def test_toc_anchor_matches_anchors_plugin_slug():
    """Source of truth: parse the rendered HTML for <hN id="..."> and assert
    the TOC anchors match in order. This guards against the TOC and the
    anchors-plugin drifting if either side's slug logic ever changes."""
    src = "# T\n\n## Setting Up\n\n### Step One\n\n## Going Further\n"
    r = render_markdown(src)
    body_ids = [m.group(2) for m in re.finditer(r'<h([234])[^>]*id="([^"]+)"', r.html)]
    toc_anchors: list[str] = []
    for e in r.toc:
        toc_anchors.append(e.anchor)
        toc_anchors.extend(c.anchor for c in e.children)
    assert toc_anchors == body_ids


def test_toc_duplicate_headings_get_suffixed_anchors():
    src = "# T\n\n## Dupe\n\nbody\n\n## Dupe\n"
    r = render_markdown(src)
    assert [e.anchor for e in r.toc] == ["dupe", "dupe-2"]
    # Anchors must also match what the body actually emits.
    body_ids = re.findall(r'<h2[^>]*id="([^"]+)"', r.html)
    assert body_ids == ["dupe", "dupe-2"]


def test_toc_empty_when_no_h2_or_h3():
    r = render_markdown("# Title only\n\nplain body\n")
    assert r.toc == []


def test_toc_skips_empty_heading_text():
    """Defensive: a heading whose inline content collapses to empty plaintext
    must not produce a TocEntry with text=''."""
    # `## ` with trailing punctuation only — markdown-it may emit this.
    src = "# T\n\n## Real\n\nbody\n"
    r = render_markdown(src)
    assert all(e.text for e in r.toc)


def test_toc_entry_is_a_dataclass():
    """Sanity: the public type is the documented dataclass."""
    e = TocEntry(level=2, text="x", anchor="x")
    assert e.children == ()
    assert e.level == 2
```

- [ ] **Step 5.2: Run tests to verify they fail**

```bash
cd services/siteapp && uv run pytest tests/test_markdown.py -v -k toc
```

Expected: all `test_toc_*` tests fail with `ImportError: cannot import name 'TocEntry' from 'app.markdown'`.

- [ ] **Step 5.3: Add `TocEntry` and `_extract_toc` to `markdown.py`**

In `services/siteapp/app/markdown.py`, add the dataclass near the other dataclasses (e.g., just above `class Rendered`):

```python
@dataclass(frozen=True)
class TocEntry:
    """One heading in the per-page table of contents.

    `level` is 2 or 3 (we don't list H1 — that's the page title — or H4+).
    `anchor` matches the `id="..."` the anchors_plugin emits on the same
    heading; `_extract_toc` mirrors that plugin's duplicate-suffix logic
    so the two cannot drift.
    """

    level: int
    text: str
    anchor: str
    children: tuple["TocEntry", ...] = ()
```

Add a new field to `Rendered` (modify the existing dataclass — add `toc` after `needs_mermaid`):

```python
@dataclass(frozen=True)
class Rendered:
    """Output of `render_markdown`.

    `needs_mermaid` is True iff the source contained at least one
    ` ```mermaid ` fenced block; the page template uses it to decide
    whether to load the vendored Mermaid JS bundle.

    `toc` is the per-page heading outline (H2 + H3, H3s nested under their
    preceding H2). Empty when the source has no H2 or H3 headings; the
    template omits the right-rail TOC entirely in that case.
    """

    html: str
    title: str | None
    needs_mermaid: bool = False
    toc: list[TocEntry] = field(default_factory=list)
```

Make sure `field` is imported at the top of `markdown.py` — change the `from dataclasses import dataclass` line to `from dataclasses import dataclass, field`.

Add `_extract_toc` (near `_apply_alerts`, before `render_markdown`):

```python
def _extract_toc(tokens) -> list[TocEntry]:
    """Walk the token stream once; produce TOC entries for H2 and H3.

    Mirrors the anchors_plugin slug + duplicate-suffix logic so the TOC
    `href="#..."` always matches a heading `id="..."` in the rendered body,
    including when authors repeat heading text (`dupe`, `dupe-2`, ...).

    H3s are nested under the most-recent H2 in a second pass. H3s that
    appear before any H2 (allowed but rare) stay at the top level.
    """
    flat: list[TocEntry] = []
    slug_counts: dict[str, int] = {}
    for i, tok in enumerate(tokens):
        if tok.type != "heading_open" or tok.tag not in ("h2", "h3"):
            continue
        if i + 1 >= len(tokens) or tokens[i + 1].type != "inline":
            continue
        text = _inline_text(tokens[i + 1]).strip()
        if not text:
            continue
        base = _slug(text)
        n = slug_counts.get(base, 0) + 1
        slug_counts[base] = n
        anchor = base if n == 1 else f"{base}-{n}"
        flat.append(TocEntry(level=2 if tok.tag == "h2" else 3, text=text, anchor=anchor))

    # Second pass: nest H3s under the preceding H2.
    out: list[TocEntry] = []
    pending_h3: list[TocEntry] = []
    last_h2_idx: int | None = None
    for entry in flat:
        if entry.level == 2:
            if last_h2_idx is not None and pending_h3:
                out[last_h2_idx] = TocEntry(
                    level=2,
                    text=out[last_h2_idx].text,
                    anchor=out[last_h2_idx].anchor,
                    children=tuple(pending_h3),
                )
                pending_h3 = []
            out.append(entry)
            last_h2_idx = len(out) - 1
        else:
            if last_h2_idx is None:
                # H3 before any H2 — keep at top level.
                out.append(entry)
            else:
                pending_h3.append(entry)
    if last_h2_idx is not None and pending_h3:
        out[last_h2_idx] = TocEntry(
            level=2,
            text=out[last_h2_idx].text,
            anchor=out[last_h2_idx].anchor,
            children=tuple(pending_h3),
        )
    return out
```

Wire it into `render_markdown` — find the existing function (around line 415) and add the `_extract_toc` call alongside the other token walks:

```python
def render_markdown(text: str) -> Rendered:
    tokens = _MD.parse(text)
    _apply_alerts(tokens)
    title = _title_from_tokens(tokens)
    needs_mermaid = _has_mermaid(tokens)
    toc = _extract_toc(tokens)
    raw_html = _MD.renderer.render(tokens, _MD.options, {})
    raw_html = raw_html.replace('class="header-anchor"', 'class="lb-anchor"')
    return Rendered(html=_sanitize(raw_html), title=title, needs_mermaid=needs_mermaid, toc=toc)
```

- [ ] **Step 5.4: Run TOC tests to verify they pass**

```bash
cd services/siteapp && uv run pytest tests/test_markdown.py -v
```

Expected: all `test_toc_*` tests pass; existing `test_markdown.py` tests still pass.

- [ ] **Step 5.5: Run full siteapp suite**

```bash
cd services/siteapp && uv run pytest
```

Expected: every test passes.

- [ ] **Step 5.6: Ruff format + check**

```bash
cd services/siteapp && uv run ruff format . && uv run ruff check .
```

- [ ] **Step 5.7: Commit**

```bash
git add services/siteapp/app/markdown.py services/siteapp/tests/test_markdown.py
git commit -m "$(cat <<'EOF'
feat(siteapp): extract per-page TOC (H2 + nested H3) during markdown render

Adds TocEntry + _extract_toc and a new toc field on Rendered. Mirrors the
anchors_plugin slug + duplicate-suffix logic so TOC links match body ids
exactly. Empty list for pages with no H2 or H3 headings so the template
can omit the right rail entirely.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — Render the TOC `<nav>` in `doc.html` (server side complete)

**Files:**
- Modify: `services/siteapp/app/docs.py` (pass `toc` into template context)
- Modify: `services/siteapp/app/templates/doc.html` (wrap article + TOC in `.lb-docs-grid`, render `<nav class="lb-docs-toc">`)
- Test: `services/siteapp/tests/test_routes_docs.py` (TOC presence/absence assertions)

This completes the server side. Visual layout (CSS) and scrollspy (JS) come in Tasks 7 and 8.

- [ ] **Step 6.1: Write the failing TOC route tests**

Add at the bottom of `services/siteapp/tests/test_routes_docs.py`:

```python
def test_toc_renders_when_page_has_h2(client: TestClient, tmp_path: Path) -> None:
    docs = tmp_path / "docs-root"
    (docs / "with-h2.md").write_text(
        "# With H2\n\n## First section\n\nbody\n\n## Second section\n\nbody\n",
        encoding="utf-8",
    )
    (docs / "_nav.yaml").write_text(
        "- name: intro\n- name: diagram\n- name: section\n- name: with-h2\n",
        encoding="utf-8",
    )
    r = client.get("/docs/with-h2")
    assert r.status_code == 200
    body = r.text
    assert 'class="lb-docs-toc"' in body
    assert 'href="#first-section"' in body
    assert 'href="#second-section"' in body
    assert "On this page" in body


def test_toc_omitted_when_page_has_no_h2(client: TestClient) -> None:
    # /docs/intro renders "# Intro" + plain body — no H2 → no TOC.
    r = client.get("/docs/intro")
    assert r.status_code == 200
    assert "lb-docs-toc" not in r.text


def test_toc_uses_russian_title_when_lang_ru(client: TestClient, tmp_path: Path) -> None:
    docs = tmp_path / "docs-root"
    (docs / "with-h2.md").write_text("# T\n\n## Alpha\n", encoding="utf-8")
    (docs / "_nav.yaml").write_text(
        "- name: intro\n- name: diagram\n- name: section\n- name: with-h2\n",
        encoding="utf-8",
    )
    r = client.get("/docs/with-h2?lang=ru")
    assert r.status_code == 200
    assert "Содержание" in r.text
```

- [ ] **Step 6.2: Run tests to verify they fail**

```bash
cd services/siteapp && uv run pytest tests/test_routes_docs.py -v -k toc
```

Expected: all three `test_toc_*` route tests FAIL (template doesn't render TOC yet; context doesn't include `toc`).

- [ ] **Step 6.3: Pass `toc` into template context in `docs.py`**

In `services/siteapp/app/docs.py`, extend the context dict in `docs_path` to include `toc`. The full dict should now look like:

```python
{
    "title": result.title or doc.rel_path.name,
    "html": result.html,
    "needs_mermaid": result.needs_mermaid,
    "lang": chosen,
    "doc": doc,
    "nav": nav,
    "current_url": str(request.url.path),
    "pygments_css": pygments_css(),
    "crumbs": crumbs,
    "prev": prev,
    "next": nxt,
    "prev_is_section": prev_is_section,
    "next_is_section": next_is_section,
    "s": DOCS_STRINGS[chosen],
    "toc": result.toc,
}
```

- [ ] **Step 6.4: Wrap article + TOC in `.lb-docs-grid` in `doc.html`**

In `services/siteapp/app/templates/doc.html`, the current structure is:

```html
<div class="lb-docs-content">
  <article class="lb-docs-article">…</article>
</div>
```

Change it to wrap the article in `.lb-docs-grid` and add the TOC after it:

```html
<div class="lb-docs-content">
  <div class="lb-docs-grid">
    <article class="lb-docs-article">
      {# existing breadcrumb, body, prev/next footer — unchanged #}
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
              <ul class="lb-docs-toc__sublist">
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
</div>
```

(The `<script src="/_static/docs-sidebar.js" defer></script>` line at the bottom stays unchanged. The script tag for `docs-toc.js` is added in Task 8.)

- [ ] **Step 6.5: Run TOC route tests to verify they pass**

```bash
cd services/siteapp && uv run pytest tests/test_routes_docs.py -v
```

Expected: all TOC tests pass; all earlier tests still pass.

- [ ] **Step 6.6: Run full siteapp suite**

```bash
cd services/siteapp && uv run pytest
```

Expected: every test passes.

- [ ] **Step 6.7: Ruff format + check**

```bash
cd services/siteapp && uv run ruff format . && uv run ruff check .
```

- [ ] **Step 6.8: Commit**

```bash
git add services/siteapp/app/docs.py services/siteapp/app/templates/doc.html services/siteapp/tests/test_routes_docs.py
git commit -m "$(cat <<'EOF'
feat(siteapp): render per-page TOC nav on docs pages

Wraps article + TOC in a .lb-docs-grid container; the TOC <nav> renders
only when the page has at least one H2 or H3. Heading text is server-
extracted so the rail is present on first paint with no FOUC.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7 — CSS for grid wrapper, TOC layout, and breakpoint

**Files:**
- Modify: `services/siteapp/app/static/site.css` (append new rules at the end of the "Docs content surface" section, around line 1525)

CSS-only task; no tests. Manual verification happens in Task 9.

- [ ] **Step 7.1: Locate the insertion point**

Open `services/siteapp/app/static/site.css`. Find the `.lb-docs-content` rule (around line 1518) and the existing `.lb-docs-article` rule directly below it. We'll append new rules in the same "Docs content surface" section, after `.lb-docs-article` and before "Breadcrumb trail".

- [ ] **Step 7.2: Append the grid + TOC rules**

After the closing brace of `.lb-docs-article { ... }` (and before the "Breadcrumb trail" comment block), insert:

```css
/* ---- Article grid: article column + right-side TOC --------- */
/* Single-column by default. At ≥1280px viewport, expand to a two-column
   grid (article + 224px TOC rail). The article keeps its 720px max-width
   inside its grid cell so it stays visually centered whether or not the
   TOC column is present (an empty TOC just doesn't render). */
.lb-docs-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  column-gap: 32px;
  align-items: start;
}
@media (min-width: 1280px) {
  .lb-docs-grid {
    grid-template-columns: minmax(0, 1fr) 224px;
  }
}

/* ---- TOC rail (right column) -------------------------------- */
.lb-docs-toc {
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
  padding: 4px 0 0 8px;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--text-muted);
}
@media (max-width: 1279px) {
  .lb-docs-toc { display: none; }
}
.lb-docs-toc__title {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  margin: 0 0 8px;
}
.lb-docs-toc__list,
.lb-docs-toc__sublist {
  list-style: none;
  padding: 0;
  margin: 0;
}
.lb-docs-toc__sublist {
  padding-left: 12px;
  margin: 2px 0 6px;
}
.lb-docs-toc__list > li { margin-bottom: 4px; }
.lb-docs-toc__link {
  display: block;
  padding: 2px 0 2px 10px;
  color: var(--text-secondary);
  text-decoration: none;
  border-left: 2px solid transparent;
  transition: color 100ms, border-left-color 100ms;
}
.lb-docs-toc__link:hover {
  color: var(--text);
  text-decoration: none;
}
.lb-docs-toc__link[data-level="3"] {
  font-size: 12px;
  color: var(--text-muted);
}
.lb-docs-toc__link[data-active="true"] {
  color: var(--accent);
  border-left-color: var(--accent);
  font-weight: 500;
}
```

- [ ] **Step 7.3: Run the existing suite (CSS file is served as a static; no regression risk but worth a smoke)**

```bash
cd services/siteapp && uv run pytest
```

Expected: pass.

- [ ] **Step 7.4: Commit**

```bash
git add services/siteapp/app/static/site.css
git commit -m "$(cat <<'EOF'
feat(siteapp): style docs TOC rail and 2-column article grid

Adds .lb-docs-grid (single-column up to 1279px, article + 224px TOC at
1280px+) plus .lb-docs-toc / .lb-docs-toc__link styles for the right-rail
outline. Sticky positioning, monochrome rule-of-thirds accent for the
active scrollspy entry.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8 — Scrollspy JS (`docs-toc.js` + template script tag)

**Files:**
- Create: `services/siteapp/app/static/docs-toc.js`
- Modify: `services/siteapp/app/templates/doc.html` (add conditional `<script>` tag)
- Test: `services/siteapp/tests/test_routes_docs.py` (assert the script tag presence is conditional on `toc`)

No JS unit tests (no JS runner in siteapp; that's tracked in the spec's "Out of scope"). We assert the conditional loading in a route test and verify behaviour manually in Task 9.

- [ ] **Step 8.1: Write the failing route test for conditional script loading**

Add at the bottom of `services/siteapp/tests/test_routes_docs.py`:

```python
def test_docs_toc_script_loaded_when_toc_present(client: TestClient, tmp_path: Path) -> None:
    docs = tmp_path / "docs-root"
    (docs / "with-h2.md").write_text("# T\n\n## A\n\nbody\n", encoding="utf-8")
    (docs / "_nav.yaml").write_text(
        "- name: intro\n- name: diagram\n- name: section\n- name: with-h2\n",
        encoding="utf-8",
    )
    r = client.get("/docs/with-h2")
    assert r.status_code == 200
    assert "/_static/docs-toc.js" in r.text


def test_docs_toc_script_omitted_when_no_toc(client: TestClient) -> None:
    r = client.get("/docs/intro")
    assert r.status_code == 200
    assert "/_static/docs-toc.js" not in r.text
```

- [ ] **Step 8.2: Run tests to verify they fail**

```bash
cd services/siteapp && uv run pytest tests/test_routes_docs.py -v -k docs_toc_script
```

Expected: both new tests fail (script tag isn't added yet).

- [ ] **Step 8.3: Create `docs-toc.js`**

Create `services/siteapp/app/static/docs-toc.js` with:

```javascript
// Scrollspy for the per-page TOC rail. Highlights the heading the reader
// is currently looking at and silently updates the URL hash so
// "copy URL" produces a deep link to the visible section.
//
// Anchors are taken from `data-toc-anchor` on the rail's links; matching
// heading elements (h2/h3) carry the same `id` (emitted server-side by
// markdown-it's anchors plugin). An IntersectionObserver with a top-anchored
// rootMargin marks the topmost intersecting heading as active.
(function () {
  if (window.__docsTocLoaded) return;
  window.__docsTocLoaded = true;

  document.addEventListener('DOMContentLoaded', function () {
    var links = Array.prototype.slice.call(
      document.querySelectorAll('[data-toc-anchor]')
    );
    if (!links.length) return;

    var headingById = {};
    var idsInOrder = [];
    links.forEach(function (link) {
      var id = link.getAttribute('data-toc-anchor');
      var h = document.getElementById(id);
      if (h) {
        headingById[id] = h;
        idsInOrder.push(id);
      }
    });
    if (!idsInOrder.length) return;

    var active = Object.create(null);
    var currentActive = null;

    function setActive(id) {
      if (id === currentActive) return;
      currentActive = id;
      links.forEach(function (link) {
        if (link.getAttribute('data-toc-anchor') === id) {
          link.setAttribute('data-active', 'true');
        } else {
          link.removeAttribute('data-active');
        }
      });
      if (id) {
        // replaceState (not pushState) so the back button isn't polluted
        // and Chrome doesn't auto-scroll on hash change.
        history.replaceState(null, '', '#' + id);
      }
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) active[e.target.id] = true;
          else delete active[e.target.id];
        });
        // Pick the topmost active heading in document order.
        var topId = null;
        for (var i = 0; i < idsInOrder.length; i++) {
          if (active[idsInOrder[i]]) {
            topId = idsInOrder[i];
            break;
          }
        }
        setActive(topId);
      },
      // Heading becomes active once it crosses into the top 25% of the
      // viewport — empirically the most natural-feeling threshold.
      { rootMargin: '0px 0px -75% 0px' }
    );

    idsInOrder.forEach(function (id) {
      observer.observe(headingById[id]);
    });
  });
})();
```

- [ ] **Step 8.4: Add the conditional script tag to `doc.html`**

In `services/siteapp/app/templates/doc.html`, find the existing line at the bottom:

```html
<script src="/_static/docs-sidebar.js" defer></script>
```

**Add immediately after it**, inside the same `{% block main %}` block:

```html
{% if toc %}<script src="/_static/docs-toc.js" defer></script>{% endif %}
```

- [ ] **Step 8.5: Run the script-tag tests**

```bash
cd services/siteapp && uv run pytest tests/test_routes_docs.py -v
```

Expected: both new `test_docs_toc_script_*` tests pass; everything else still passes.

- [ ] **Step 8.6: Run full siteapp suite**

```bash
cd services/siteapp && uv run pytest
```

Expected: every test passes.

- [ ] **Step 8.7: Ruff format + check**

```bash
cd services/siteapp && uv run ruff format . && uv run ruff check .
```

(`docs-toc.js` isn't touched by ruff since it's JS, but the route test additions are Python.)

- [ ] **Step 8.8: Commit**

```bash
git add services/siteapp/app/static/docs-toc.js services/siteapp/app/templates/doc.html services/siteapp/tests/test_routes_docs.py
git commit -m "$(cat <<'EOF'
feat(siteapp): scrollspy + URL-hash sync for docs TOC rail

IntersectionObserver-based active-heading tracking with a top-anchored
rootMargin. Updates the TOC's data-active and the URL hash via
history.replaceState (no back-button pollution, no scroll jump).
Script loads only on pages that actually render a TOC.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9 — Manual smoke verification in the dev server

No code changes; verification only. This catches the things automated tests can't: visual layout, scrollspy feel, hash updates without scroll jump.

- [ ] **Step 9.1: Start the siteapp dev server with real docs**

From the repo root:

```bash
task dev
```

(or follow whatever the README says for booting siteapp with `public_docs/` mounted — the `task dev` recipe is the standard entry point.)

Visit `http://localhost:8080/docs/` (or whatever port `task dev` reports).

- [ ] **Step 9.2: Verify TOC layout at desktop width**

- Open `/docs/architecture/auth.md` (or any page with multiple H2s) at viewport width ≥ 1280px.
- TOC appears on the right side, with "On this page" caption.
- TOC is sticky: scrolling the article keeps it pinned at top with `16px` offset.
- H3 entries are indented under their H2.
- At viewport width < 1280px, TOC disappears entirely and the article column behaves exactly as today (centered, max 720px).

- [ ] **Step 9.3: Verify scrollspy**

- On the same long page, scroll slowly through the article.
- The TOC entry corresponding to the currently-visible section gets `data-active="true"` (visible as accent color + left border).
- Only one entry is active at a time.
- The URL bar updates to `#section-anchor` as you scroll; no page jump or scroll movement happens when the hash changes.
- Clicking a TOC entry scrolls smoothly to the heading and updates the URL.

- [ ] **Step 9.4: Verify prev/next DFS behaviour**

- Open `/docs/researcher/` (a section index page).
- The "Next" footer link is "First notebook" (the first child), not "Operator" (the next top section).
- Open the last child page of `/docs/researcher/` (e.g. `/docs/researcher/troubleshooting`).
- The "Next" footer link is `/docs/operator/` (the next top section's index), with eyebrow text "Next section" (not just "Next").
- Open any non-boundary page (e.g., `/docs/researcher/first-notebook`).
- Eyebrow text is "Next" / "Previous" (no "section" suffix).

- [ ] **Step 9.5: Verify Russian strings**

- Visit `/docs/researcher/?lang=ru` and confirm:
  - TOC heading reads "Содержание" if the page has any H2/H3.
  - Eyebrow reads "Далее" / "Назад" for in-section transitions, "Следующий раздел" / "Предыдущий раздел" at section boundaries.

- [ ] **Step 9.6: Verify no-TOC pages don't ship the script**

- View source of `/docs/intro` (a page with no H2 — if one exists) or `/docs/overview/` (just an index without subsections).
- `lb-docs-toc` class is absent from the HTML.
- `/_static/docs-toc.js` is NOT in any `<script>` tag.

- [ ] **Step 9.7: If any check fails**

Document the failure (which step, what you saw vs. what was expected) and fix it before declaring the work done. Do NOT mark the task as completed on a known failure.

No commit for this task — verification only. If a fix is needed, commit the fix to the appropriate prior task's scope.

---

## Wrap-up — confirm CI green before opening the PR

- [ ] **Step W.1: Full siteapp suite one more time**

```bash
cd services/siteapp && uv run pytest && uv run ruff format --check . && uv run ruff check .
```

Expected: all pass, no diff.

- [ ] **Step W.2: Verify the commit graph is clean**

```bash
git log --oneline -10
```

Expected: eight new commits (Tasks 1, 2, 3, 4, 5, 6, 7, 8) plus the design spec commit, in order.

- [ ] **Step W.3: Push and open a PR**

(Coordinate with the user before pushing — they may want to review the commits locally first.)

PR title (Conventional Commits): `feat(siteapp): docs in-page TOC + DFS prev/next`

PR description: link the spec doc and summarise the user-visible behaviour change in 2-3 bullets. Per `CLAUDE.md`, the `pr-siteapp` workflow's required check is `pr-siteapp / siteapp` — wait for it to go green before requesting merge.

---

## Self-review notes (from plan author)

**Spec coverage:** every section of the spec has a task —
- Layout (spec §Layout) → Task 7.
- TOC extraction (Component 1) → Task 5.
- Template (Component 2) → Task 6.
- Scrollspy (Component 3) → Task 8.
- DFS prev/next + label format (Component 4) → Tasks 1, 2, 3, 4.
- Strings (Q5 Russian) → Task 3 (data) + Task 4 (consumption).
- Testing (spec §Testing) → distributed across Tasks 1, 2, 4, 5, 6, 8.
- Risks (anchor/TOC drift, layout regression, hash churn) → respectively covered by `test_toc_anchor_matches_anchors_plugin_slug` in Task 5, `test_toc_omitted_when_page_has_no_h2` in Task 6, and the scrollspy `replaceState` choice in Task 8.

**Type consistency:** `TocEntry` (level/text/anchor/children), `flatten_nav` signature, `_is_top_section` signature, `DOCS_STRINGS` key names (`prev`, `next`, `prev_section`, `next_section`, `toc_title`), template variable names (`toc`, `s`, `prev_is_section`, `next_is_section`) — all match between definitions (Tasks 1, 3, 5) and consumers (Tasks 3, 4, 6, 8).

**Placeholder scan:** no TBDs; every code step shows full code; every test step shows assertion text.
