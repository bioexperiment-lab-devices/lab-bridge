from __future__ import annotations

from pathlib import Path

import pytest

from app.nav import build_nav


@pytest.fixture
def tree(site_data: Path) -> Path:
    d = site_data / "docs"
    (d / "index.md").write_text("# Home\n", encoding="utf-8")
    (d / "index.ru.md").write_text("# Главная\n", encoding="utf-8")
    (d / "guide.md").write_text("# Guide\n", encoding="utf-8")
    sec = d / "advanced"
    sec.mkdir()
    (sec / "index.md").write_text("# Advanced\n", encoding="utf-8")
    (sec / "deep.md").write_text("# Deep dive\n", encoding="utf-8")
    return d


def test_top_level_order_dirs_then_files(tree: Path) -> None:
    nav = build_nav(tree)
    titles_en = [e.title_en for e in nav]
    # 'advanced' (dir) before 'index' before 'guide' alphabetically isn't
    # what we want — directories first, then files alphabetically by name.
    assert titles_en == ["Advanced", "Home", "Guide"]


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
