from __future__ import annotations

from pathlib import Path

import pytest

from app.translations import DocFile, find_doc, resolve_lang_file


@pytest.fixture
def docs(site_data: Path) -> Path:
    docs_root = site_data / "docs"
    (docs_root / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (docs_root / "intro.ru.md").write_text("# Введение\n", encoding="utf-8")
    section = docs_root / "section"
    section.mkdir()
    (section / "index.md").write_text("# Section\n", encoding="utf-8")
    (section / "page.md").write_text("# Page\n", encoding="utf-8")
    return docs_root


def test_find_doc_root_index(docs: Path) -> None:
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    doc = find_doc(docs, "")
    assert doc is not None
    assert doc.rel_path == Path("index")
    assert doc.en_exists is True


def test_find_doc_file(docs: Path) -> None:
    doc = find_doc(docs, "intro")
    assert doc is not None
    assert doc.rel_path == Path("intro")
    assert doc.ru_exists is True


def test_find_doc_directory_index(docs: Path) -> None:
    doc = find_doc(docs, "section/")
    assert doc is not None
    assert doc.rel_path == Path("section/index")
    assert doc.ru_exists is False


def test_find_doc_missing_returns_none(docs: Path) -> None:
    assert find_doc(docs, "nope") is None


def test_find_doc_traversal_returns_none(docs: Path) -> None:
    assert find_doc(docs, "../etc/passwd") is None


def test_resolve_lang_file_english(docs: Path) -> None:
    doc = find_doc(docs, "intro")
    assert doc is not None
    path = resolve_lang_file(docs, doc, "en")
    assert path == docs / "intro.md"


def test_resolve_lang_file_russian(docs: Path) -> None:
    doc = find_doc(docs, "intro")
    assert doc is not None
    path = resolve_lang_file(docs, doc, "ru")
    assert path == docs / "intro.ru.md"


def test_resolve_lang_file_falls_back_to_english(docs: Path) -> None:
    doc = find_doc(docs, "section/page")
    assert doc is not None
    path = resolve_lang_file(docs, doc, "ru")
    assert path == docs / "section" / "page.md"


def test_find_doc_section_without_slash_returns_none(docs: Path) -> None:
    """Without trailing slash, `section` is treated as a file `section.md`,
    not as the section's index. Since no `section.md` exists, the result is None.
    This pins the trailing-slash contract at this layer."""
    assert find_doc(docs, "section") is None


def test_find_doc_orphan_ru_only_returns_none(site_data: Path) -> None:
    """A foo.ru.md without a matching foo.md must be ignored — English is
    the source of truth."""
    docs_root = site_data / "docs"
    (docs_root / "only.ru.md").write_text("# Только\n", encoding="utf-8")
    assert find_doc(docs_root, "only") is None
