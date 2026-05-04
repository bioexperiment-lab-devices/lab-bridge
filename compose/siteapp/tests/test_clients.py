from __future__ import annotations

from pathlib import Path

import pytest

from app.clients import CHISEL_HOST, load_roster


def test_happy_path(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"khamit_desktop": 8089, "another_lab": 8090}', encoding="utf-8")

    assert load_roster(f) == {
        "khamit_desktop": {"host": CHISEL_HOST, "port": 8089},
        "another_lab": {"host": CHISEL_HOST, "port": 8090},
    }


def test_empty_roster(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text("{}", encoding="utf-8")

    assert load_roster(f) == {}


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        load_roster(tmp_path / "nope.json")


def test_malformed_json_raises(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text("not-json", encoding="utf-8")

    with pytest.raises(ValueError):  # json.JSONDecodeError is a ValueError
        load_roster(f)


def test_top_level_not_object_raises(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


def test_non_int_value_raises(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"x": "not-a-port"}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


def test_bool_value_rejected(tmp_path: Path) -> None:
    # YAML "yes"/"no" can render as true/false; reject those explicitly
    # because isinstance(True, int) is True in Python.
    f = tmp_path / "clients.json"
    f.write_text('{"x": true}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)
