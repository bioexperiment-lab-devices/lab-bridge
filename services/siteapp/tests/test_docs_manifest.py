from __future__ import annotations

from pathlib import Path

import pytest

from app.docs_manifest import (
    DocsNavError,
    ManifestEntry,
    has_md_descendants,
    load_dir_manifest,
    parse_manifest_yaml,
)


SRC = Path("public_docs/_nav.yaml")


def test_parses_minimal_entry() -> None:
    entries = parse_manifest_yaml("- name: intro\n", SRC)
    assert entries == [ManifestEntry(name="intro", title=None, hidden=False)]


def test_parses_full_entry() -> None:
    text = """
- name: admin
  title: Administrator guide
  hidden: false
- name: draft
  hidden: true
"""
    entries = parse_manifest_yaml(text, SRC)
    assert entries == [
        ManifestEntry(name="admin", title="Administrator guide", hidden=False),
        ManifestEntry(name="draft", title=None, hidden=True),
    ]


def test_empty_list_is_valid() -> None:
    assert parse_manifest_yaml("[]\n", SRC) == []


def test_empty_file_is_valid() -> None:
    # Treat a file that parses to None (empty document) as an empty list.
    assert parse_manifest_yaml("", SRC) == []


def test_root_must_be_list() -> None:
    with pytest.raises(DocsNavError, match="must be a YAML list"):
        parse_manifest_yaml("name: intro\n", SRC)


def test_entry_must_be_mapping() -> None:
    with pytest.raises(DocsNavError, match="entry #1 must be a mapping"):
        parse_manifest_yaml("- intro\n", SRC)


def test_missing_name_field() -> None:
    with pytest.raises(DocsNavError, match="entry #1 is missing required 'name'"):
        parse_manifest_yaml("- title: foo\n", SRC)


def test_unknown_field_rejected() -> None:
    with pytest.raises(DocsNavError, match="unknown field 'order'"):
        parse_manifest_yaml("- name: intro\n  order: 5\n", SRC)


def test_duplicate_name_rejected() -> None:
    text = "- name: intro\n- name: intro\n"
    with pytest.raises(DocsNavError, match="duplicate entry 'intro'"):
        parse_manifest_yaml(text, SRC)


def test_name_must_be_string() -> None:
    with pytest.raises(DocsNavError, match="'name' must be a string"):
        parse_manifest_yaml("- name: 5\n", SRC)


def test_title_must_be_string() -> None:
    with pytest.raises(DocsNavError, match="'title' must be a string"):
        parse_manifest_yaml("- name: intro\n  title: 5\n", SRC)


def test_hidden_must_be_bool() -> None:
    with pytest.raises(DocsNavError, match="'hidden' must be a bool"):
        parse_manifest_yaml("- name: intro\n  hidden: yes-please\n", SRC)


def test_invalid_yaml_syntax() -> None:
    with pytest.raises(DocsNavError, match="invalid YAML"):
        parse_manifest_yaml("- name: [unclosed\n", SRC)


def test_error_includes_source_path() -> None:
    with pytest.raises(DocsNavError, match=str(SRC)):
        parse_manifest_yaml("- name: 5\n", SRC)


def _w(path: Path, content: str = "# H\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_dir_returns_entries_in_manifest_order(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: beta\n- name: alpha\n")
    _w(tmp_path / "alpha.md")
    _w(tmp_path / "beta.md")
    entries = load_dir_manifest(tmp_path)
    assert [e.name for e in entries] == ["beta", "alpha"]


def test_load_dir_missing_manifest_raises(tmp_path: Path) -> None:
    _w(tmp_path / "alpha.md")
    with pytest.raises(DocsNavError, match="_nav.yaml not found"):
        load_dir_manifest(tmp_path)


def test_load_dir_no_manifest_required_when_only_index(tmp_path: Path) -> None:
    _w(tmp_path / "index.md")
    assert load_dir_manifest(tmp_path) == []


def test_load_dir_no_manifest_required_for_asset_only_dir(tmp_path: Path) -> None:
    _w(tmp_path / "logo.svg", "<svg/>")
    assert load_dir_manifest(tmp_path) == []


def test_load_dir_unknown_entry_raises(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: ghost\n")
    with pytest.raises(DocsNavError, match="ghost.*no ghost.md or ghost/index.md"):
        load_dir_manifest(tmp_path)


def test_load_dir_unlisted_file_raises(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: alpha\n")
    _w(tmp_path / "alpha.md")
    _w(tmp_path / "beta.md")
    with pytest.raises(DocsNavError, match="beta.md exists but is not in _nav.yaml"):
        load_dir_manifest(tmp_path)


def test_load_dir_unlisted_subdir_raises(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "[]\n")
    _w(tmp_path / "sub" / "index.md")
    with pytest.raises(DocsNavError, match="sub/ exists but is not in _nav.yaml"):
        load_dir_manifest(tmp_path)


def test_load_dir_resolves_entry_to_subdir(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: section\n")
    _w(tmp_path / "section" / "index.md")
    entries = load_dir_manifest(tmp_path)
    assert [e.name for e in entries] == ["section"]


def test_load_dir_resolves_entry_to_file_when_both_exist(tmp_path: Path) -> None:
    # Ambiguous on disk: foo.md and foo/index.md both exist. The validator
    # picks the file. This is a corner case (authors shouldn't do this); the
    # rule exists so the lookup is deterministic.
    _w(tmp_path / "_nav.yaml", "- name: foo\n")
    _w(tmp_path / "foo.md")
    _w(tmp_path / "foo" / "index.md")
    entries = load_dir_manifest(tmp_path)
    assert [e.name for e in entries] == ["foo"]


def test_load_dir_ignores_translation_files(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: intro\n")
    _w(tmp_path / "intro.md")
    _w(tmp_path / "intro.ru.md", "# Введение\n")
    # Translation file does not need its own manifest entry.
    entries = load_dir_manifest(tmp_path)
    assert [e.name for e in entries] == ["intro"]


def test_load_dir_collects_all_errors(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: ghost\n")
    _w(tmp_path / "real.md")
    # Two violations: unknown 'ghost' and unlisted 'real.md'. Both should
    # surface in the same exception so authors fix everything at once.
    with pytest.raises(DocsNavError) as excinfo:
        load_dir_manifest(tmp_path)
    msg = str(excinfo.value)
    assert "ghost" in msg
    assert "real.md" in msg


def test_has_md_descendants_true_for_section(tmp_path: Path) -> None:
    _w(tmp_path / "sub" / "index.md")
    assert has_md_descendants(tmp_path) is True


def test_has_md_descendants_false_for_assets(tmp_path: Path) -> None:
    _w(tmp_path / "logo.svg", "<svg/>")
    assert has_md_descendants(tmp_path) is False
