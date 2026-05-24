from __future__ import annotations

from pathlib import Path

import pytest

from app.docs import build_breadcrumb, prev_next
from app.nav import NavEntry, build_nav, flatten_nav


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    (d / "index.md").write_text("# Home\n", encoding="utf-8")
    (d / "index.ru.md").write_text("# Главная\n", encoding="utf-8")
    (d / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
    (d / "guide.md").write_text("# Guide\n", encoding="utf-8")
    sec = d / "advanced"
    sec.mkdir()
    (sec / "index.md").write_text("# Advanced\n", encoding="utf-8")
    (sec / "deep.md").write_text("# Deep dive\n", encoding="utf-8")
    (sec / "_nav.yaml").write_text("- name: deep\n", encoding="utf-8")
    (d / "_nav.yaml").write_text(
        "- name: advanced\n- name: alpha\n- name: guide\n", encoding="utf-8"
    )
    return d


def test_top_level_order_follows_manifest(tree: Path) -> None:
    nav = build_nav(tree)
    titles_en = [e.title_en for e in nav]
    assert titles_en == ["Home", "Advanced", "Alpha", "Guide"]


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


def test_filename_fallback_when_no_h1(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    (d / "no-heading.md").write_text("just a paragraph\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: no-heading\n", encoding="utf-8")
    nav = build_nav(d)
    entry = next(e for e in nav if e.url == "/docs/no-heading")
    assert entry.title_en == "no-heading"


def test_orphan_ru_file_is_ignored(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    (d / "only-ru.ru.md").write_text("# Только\n", encoding="utf-8")
    nav = build_nav(d)
    assert all(e.url != "/docs/only-ru" for e in nav)


def test_section_title_falls_back_to_dir_name(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    sec = d / "untitled"
    sec.mkdir()
    (sec / "index.md").write_text("just a paragraph\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: untitled\n", encoding="utf-8")
    nav = build_nav(d)
    entry = next(e for e in nav if e.url == "/docs/untitled/")
    assert entry.title_en == "untitled"


def test_empty_dir_is_skipped(tmp_path: Path) -> None:
    # An asset-only / empty subdirectory needs no manifest entry. The parent
    # also doesn't need a manifest if nothing is listable at its level.
    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    (d / "empty").mkdir()
    nav = build_nav(d)
    assert all(e.url != "/docs/empty/" for e in nav)


def _sample_nav() -> list:
    return [
        NavEntry(
            title_en="Researchers",
            title_ru=None,
            url="/docs/researcher/",
            children=(
                NavEntry(
                    title_en="First notebook", title_ru=None, url="/docs/researcher/first-notebook"
                ),
            ),
        ),
        NavEntry(title_en="Architecture", title_ru=None, url="/docs/architecture/"),
    ]


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
                NavEntry(
                    title_en="First notebook", title_ru=None, url="/docs/researcher/first-notebook"
                ),
                NavEntry(
                    title_en="Working with devices",
                    title_ru=None,
                    url="/docs/researcher/working-with-devices",
                ),
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


def test_breadcrumb_for_nested_doc():
    crumbs = build_breadcrumb(_sample_nav(), "/docs/researcher/first-notebook")
    assert [c["title"] for c in crumbs] == ["Docs", "Researchers", "First notebook"]


def test_breadcrumb_for_root_doc():
    crumbs = build_breadcrumb(_sample_nav(), "/docs/architecture/")
    assert [c["title"] for c in crumbs] == ["Docs", "Architecture"]


def test_prev_next_in_section():
    # Single-child section: first-notebook has no siblings → both None.
    prev, nxt = prev_next(_sample_nav(), "/docs/researcher/first-notebook")
    assert prev is None and nxt is None


def test_prev_next_across_top_level():
    nav = _sample_nav()
    prev, nxt = prev_next(nav, "/docs/architecture/")
    # Architecture comes after Researchers section in the sample manifest order.
    assert prev is not None and prev.title_en == "Researchers"
    assert nxt is None


def test_manifest_drives_root_order(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    (d / "index.md").write_text("# Home\n", encoding="utf-8")
    (d / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
    (d / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: guide\n- name: alpha\n", encoding="utf-8")
    nav = build_nav(d)
    assert [e.title_en for e in nav] == ["Home", "Guide", "Alpha"]


def test_manifest_title_override(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    (d / "intro.md").write_text("# Long intro heading\n", encoding="utf-8")
    (d / "_nav.yaml").write_text('- name: intro\n  title: "Intro"\n', encoding="utf-8")
    nav = build_nav(d)
    intro = next(e for e in nav if e.url == "/docs/intro")
    assert intro.title_en == "Intro"


def test_manifest_hidden_omits_from_nav(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    (d / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (d / "draft.md").write_text("# Draft\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: intro\n- name: draft\n  hidden: true\n", encoding="utf-8")
    nav = build_nav(d)
    urls = [e.url for e in nav]
    assert "/docs/intro" in urls
    assert "/docs/draft" not in urls


def test_manifest_home_pinned_first(tmp_path: Path) -> None:
    # Even if the root manifest lists other things first, Home (the root
    # index.md) is implicit and pinned at position 0.
    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    (d / "index.md").write_text("# Home\n", encoding="utf-8")
    (d / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: intro\n", encoding="utf-8")
    nav = build_nav(d)
    assert nav[0].url == "/docs/"
    assert nav[1].url == "/docs/intro"


def test_manifest_section_walks_subdir_manifest(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    sec = d / "researcher"
    sec.mkdir(parents=True)
    (d / "_nav.yaml").write_text("- name: researcher\n", encoding="utf-8")
    (sec / "index.md").write_text("# Researcher\n", encoding="utf-8")
    (sec / "first-notebook.md").write_text("# First notebook\n", encoding="utf-8")
    (sec / "_nav.yaml").write_text("- name: first-notebook\n", encoding="utf-8")
    nav = build_nav(d)
    researcher = next(e for e in nav if e.url == "/docs/researcher/")
    assert [c.url for c in researcher.children] == ["/docs/researcher/first-notebook"]


def test_strict_mode_missing_manifest_raises(tmp_path: Path) -> None:
    from app.docs_manifest import DocsNavError

    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    (d / "intro.md").write_text("# Intro\n", encoding="utf-8")
    with pytest.raises(DocsNavError, match="_nav.yaml not found"):
        build_nav(d)


def test_strict_mode_unlisted_file_raises(tmp_path: Path) -> None:
    from app.docs_manifest import DocsNavError

    d = tmp_path / "docs-root"
    d.mkdir(exist_ok=True)
    (d / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (d / "extra.md").write_text("# Extra\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: intro\n", encoding="utf-8")
    with pytest.raises(DocsNavError, match="extra.md exists but is not in _nav.yaml"):
        build_nav(d)
