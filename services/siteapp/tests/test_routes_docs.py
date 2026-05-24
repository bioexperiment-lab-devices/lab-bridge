from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
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
    return TestClient(app.main.app)


def test_docs_index_renders(client: TestClient) -> None:
    r = client.get("/docs/")
    assert r.status_code == 200
    assert "Welcome" in r.text


def test_page_renders(client: TestClient) -> None:
    r = client.get("/docs/intro")
    assert r.status_code == 200
    assert "hello world" in r.text


def test_directory_without_slash_redirects(client: TestClient) -> None:
    r = client.get("/docs/section", follow_redirects=False)
    assert r.status_code == 308
    assert r.headers["location"].endswith("/docs/section/")


def test_lang_query_switches_to_russian(client: TestClient) -> None:
    r = client.get("/docs/intro?lang=ru")
    assert r.status_code == 200
    assert "привет" in r.text


def test_lang_falls_back_to_english(client: TestClient) -> None:
    r = client.get("/docs/section/page?lang=ru")
    assert r.status_code == 200
    assert "Page" in r.text


def test_lang_cookie_persists(client: TestClient) -> None:
    r = client.get("/docs/intro?lang=ru", follow_redirects=False)
    assert r.cookies.get("lang") == "ru"
    client.cookies.set("lang", "ru")
    r2 = client.get("/docs/intro")
    assert "привет" in r2.text


def test_missing_returns_404(client: TestClient) -> None:
    assert client.get("/docs/nope").status_code == 404


def test_childless_top_section_renders_as_section_folder_without_chevron(
    client: TestClient, tmp_path: Path
) -> None:
    """A top-level section with only an index.md should still render as a
    section header (data-top-section folder row), but with no chevron toggle
    button (nothing to expand)."""
    docs = tmp_path / "docs-root"
    solo = docs / "solo"
    solo.mkdir()
    (solo / "index.md").write_text("# Solo Section\n", encoding="utf-8")
    (docs / "_nav.yaml").write_text(
        "- name: solo\n- name: intro\n- name: diagram\n- name: section\n",
        encoding="utf-8",
    )
    r = client.get("/docs/intro")
    assert r.status_code == 200
    body = r.text
    # /docs/solo/ entry exists as a folder row with data-top-section,
    # but has no toggle button (no children) and no children container.
    assert 'class="lb-docs-side__folder" data-level="0" data-top-section="true"' in body
    assert 'href="/docs/solo/"' in body
    # The chevron toggle for /docs/solo/ must NOT be emitted.
    assert 'data-section-key="/docs/solo/"' not in body


def test_active_top_section_label_marks_data_active(client: TestClient, tmp_path: Path) -> None:
    """When the user is ON a top section's index page, the section's label
    carries data-active so CSS can color it black (not muted)."""
    docs = tmp_path / "docs-root"
    solo = docs / "solo"
    solo.mkdir()
    (solo / "index.md").write_text("# Solo Section\n", encoding="utf-8")
    (docs / "_nav.yaml").write_text(
        "- name: solo\n- name: intro\n- name: diagram\n- name: section\n",
        encoding="utf-8",
    )
    r = client.get("/docs/solo/")
    assert r.status_code == 200
    body = r.text
    # Active state on the top-section folder label so the CSS rule
    # `[data-top-section="true"][data-active="true"]` kicks in.
    assert (
        'class="lb-docs-side__item lb-docs-side__item--folder"\n'
        '         data-level="0"\n'
        '         data-top-section="true"\n'
        '         data-active="true"' in body
    )


def test_docs_root_without_index_redirects_to_first_nav(client: TestClient, tmp_path: Path) -> None:
    """When the root has no index.md, /docs/ should redirect to the first
    sidebar entry instead of 404'ing."""
    (tmp_path / "docs-root" / "index.md").unlink()
    r = client.get("/docs/", follow_redirects=False)
    assert r.status_code == 308
    assert r.headers["location"] == "/docs/intro"


def test_orphan_ru_only_returns_404(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "docs-root" / "only.ru.md").write_text("# Только\n", encoding="utf-8")
    assert client.get("/docs/only").status_code == 404


def test_url_encoded_traversal_returns_404_not_redirect(client: TestClient) -> None:
    """A URL-encoded `..` segment must not leak directory existence via 308.
    Without safe_join, `/docs/..%2Fagent` would 308 to `/docs/../agent/`.
    With safe_join, traversal is treated like a missing doc -> 404."""
    r = client.get("/docs/..%2Fagent", follow_redirects=False)
    assert r.status_code == 404


def test_diagram_page_loads_mermaid_script(client: TestClient) -> None:
    r = client.get("/docs/diagram")
    assert r.status_code == 200
    assert "/_static/mermaid-init.js" in r.text


def test_plain_page_does_not_load_mermaid_script(client: TestClient) -> None:
    r = client.get("/docs/intro")
    assert r.status_code == 200
    assert "/_static/mermaid-init.js" not in r.text


def test_mermaid_init_re_renders_on_theme_change(client: TestClient) -> None:
    """Guard the no-reload theme switch: mermaid-init.js must observe
    <html data-theme> and re-run, otherwise toggling the site theme leaves
    diagrams stuck in their original colors until the user reloads."""
    r = client.get("/_static/mermaid-init.js")
    assert r.status_code == 200
    body = r.text
    assert "MutationObserver" in body, "missing observer that re-renders on theme flip"
    assert "data-theme" in body, "observer must watch data-theme"
    assert "data-processed" in body, "must clear mermaid's processed flag before re-run"


def test_doc_static_svg_is_served(client: TestClient) -> None:
    r = client.get("/docs/icons/jupyter.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in r.content


def test_doc_static_disallowed_extension_is_404(client: TestClient) -> None:
    r = client.get("/docs/icons/secret.exe")
    assert r.status_code == 404


def test_doc_static_missing_file_is_404(client: TestClient) -> None:
    r = client.get("/docs/icons/nope.svg")
    assert r.status_code == 404


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


def test_prevnext_back_to_own_section_index_says_previous_not_section(
    client: TestClient,
) -> None:
    """On /docs/section/page, the prev link points to /docs/section/ (the
    page's OWN section index). The eyebrow must read "Previous", not
    "Previous section" — the user is staying within Section, not crossing
    into a new top-level chapter. Guards the ancestor-exclusion in
    _is_top_section."""
    r = client.get("/docs/section/page")
    assert r.status_code == 200
    body = r.text
    # The prev link target is /docs/section/ (we are the first child).
    assert 'href="/docs/section/"' in body
    # But the eyebrow stays "Previous" (no "Previous section").
    assert "Previous section" not in body


def test_prevnext_omitted_on_single_entry_nav(tmp_path: Path, monkeypatch) -> None:
    """When the nav has exactly one entry (Home), prev = next = None and
    the footer doesn't render — matches today's `{% if prev or next %}` guard."""
    docs = tmp_path / "docs-root"
    # Wipe everything the fixture created; leave only Home.
    for child in list(docs.iterdir()):
        if child.is_file():
            child.unlink()
        else:
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


def test_toc_nav_aria_label_tracks_language(client: TestClient, tmp_path: Path) -> None:
    """The TOC <nav> landmark name is derived from the visible title via
    aria-labelledby, so screen readers announce the localised name (not a
    hardcoded English string)."""
    docs = tmp_path / "docs-root"
    (docs / "with-h2.md").write_text("# T\n\n## Alpha\n", encoding="utf-8")
    (docs / "_nav.yaml").write_text(
        "- name: intro\n- name: diagram\n- name: section\n- name: with-h2\n",
        encoding="utf-8",
    )
    en = client.get("/docs/with-h2").text
    ru = client.get("/docs/with-h2?lang=ru").text
    # Both pages use aria-labelledby; the actual landmark name comes from
    # the linked element's localized text content.
    assert 'aria-labelledby="lb-docs-toc-heading"' in en
    assert 'aria-labelledby="lb-docs-toc-heading"' in ru
    # No hardcoded English aria-label remains.
    assert 'aria-label="On this page"' not in en
    assert 'aria-label="On this page"' not in ru


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


def test_toc_renders_h3_nested_under_h2(client: TestClient, tmp_path: Path) -> None:
    """The {% if h.children %} sublist branch in doc.html is otherwise only
    exercised at the unit-test layer. Without this route test, a Jinja
    refactor could silently break the H3 rendering."""
    docs = tmp_path / "docs-root"
    (docs / "with-h3.md").write_text(
        "# Title\n\n## Alpha\n\n### Sub-alpha\n\n## Beta\n",
        encoding="utf-8",
    )
    (docs / "_nav.yaml").write_text(
        "- name: intro\n- name: diagram\n- name: section\n- name: with-h3\n",
        encoding="utf-8",
    )
    r = client.get("/docs/with-h3")
    assert r.status_code == 200
    body = r.text
    assert 'class="lb-docs-toc__sublist"' in body
    assert 'href="#sub-alpha"' in body
    assert 'data-level="3"' in body
