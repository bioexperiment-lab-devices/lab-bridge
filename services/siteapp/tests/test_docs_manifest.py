from __future__ import annotations

from pathlib import Path

import pytest

from app.docs_manifest import (
    DocsNavError,
    ManifestEntry,
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
