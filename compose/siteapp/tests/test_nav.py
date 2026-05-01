from __future__ import annotations

from pathlib import Path

import pytest

from app.nav import build_nav


@pytest.fixture
def tree(site_data: Path) -> Path:
    d = site_data / "docs"
    (d / "index.md").write_text("# Home\n", encoding="utf-8")
    (d / "index.ru.md").write_text("# Главная\n", encoding="utf-8")
    (d / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
    (d / "guide.md").write_text("# Guide\n", encoding="utf-8")
    sec = d / "advanced"
    sec.mkdir()
    (sec / "index.md").write_text("# Advanced\n", encoding="utf-8")
    (sec / "deep.md").write_text("# Deep dive\n", encoding="utf-8")
    return d


def test_top_level_order_dirs_then_files(tree: Path) -> None:
    nav = build_nav(tree)
    titles_en = [e.title_en for e in nav]
    # Directories first, then Home (the root index.md), then remaining files alphabetical.
    # The 'alpha' file is intentionally ordered to ensure Home-first ordering is the
    # actual behavior under test (not a coincidence of strict alphabetical sort).
    assert titles_en == ["Advanced", "Home", "Alpha", "Guide"]


def test_translation_title_when_present(tree: Path) -> None:
    nav = build_nav(tree)
    home = next(e for e in nav if e.url == "/docs/")
    assert home.title_en == "Home"
    assert home.title_ru == "Главная"


def test_no_translation_yields_none(tree: Path) -> None:
    nav = build_nav(tree)
    guide = next(e for e in nav if e.url == "/docs/guide")
    assert guide.title_ru is None


def test_directory_url_has_trailing_slash(tree: Path) -> None:
    nav = build_nav(tree)
    advanced = next(e for e in nav if e.title_en == "Advanced")
    assert advanced.url == "/docs/advanced/"
    assert {c.url for c in advanced.children} == {"/docs/advanced/deep"}


def test_filename_fallback_when_no_h1(site_data: Path) -> None:
    d = site_data / "docs"
    (d / "no-heading.md").write_text("just a paragraph\n", encoding="utf-8")
    nav = build_nav(d)
    entry = next(e for e in nav if e.url == "/docs/no-heading")
    assert entry.title_en == "no-heading"


def test_orphan_ru_file_is_ignored(site_data: Path) -> None:
    d = site_data / "docs"
    (d / "only-ru.ru.md").write_text("# Только\n", encoding="utf-8")
    nav = build_nav(d)
    assert all(e.url != "/docs/only-ru" for e in nav)


def test_section_title_falls_back_to_dir_name(site_data: Path) -> None:
    d = site_data / "docs"
    sec = d / "untitled"
    sec.mkdir()
    (sec / "index.md").write_text("just a paragraph\n", encoding="utf-8")
    nav = build_nav(d)
    entry = next(e for e in nav if e.url == "/docs/untitled/")
    assert entry.title_en == "untitled"


def test_dir_without_index_uses_dir_name(site_data: Path) -> None:
    d = site_data / "docs"
    sec = d / "loose"
    sec.mkdir()
    (sec / "page.md").write_text("# Page\n", encoding="utf-8")
    nav = build_nav(d)
    entry = next(e for e in nav if e.url == "/docs/loose/")
    assert entry.title_en == "loose"
    assert entry.title_ru is None
    assert {c.url for c in entry.children} == {"/docs/loose/page"}


def test_empty_dir_is_skipped(site_data: Path) -> None:
    d = site_data / "docs"
    (d / "empty").mkdir()
    nav = build_nav(d)
    assert all(e.url != "/docs/empty/" for e in nav)
