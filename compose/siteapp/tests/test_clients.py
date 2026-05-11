from __future__ import annotations

from pathlib import Path

import pytest

from app.clients import CHISEL_HOST, load_roster


def test_happy_path(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text(
        '{"khamit_desktop": {"port": 8089, "password_sha256": "aa"},'
        ' "another_lab": {"port": 8090, "password_sha256": "bb"}}',
        encoding="utf-8",
    )

    assert load_roster(f) == {
        "khamit_desktop": {"host": CHISEL_HOST, "port": 8089},
        "another_lab": {"host": CHISEL_HOST, "port": 8090},
    }


def test_rejects_old_flat_shape(tmp_path: Path) -> None:
    # The flat {name: int} shape was the pre-2026-05-11 format. After the
    # renderer change, an int value means a stale clients.json on the VPS.
    f = tmp_path / "clients.json"
    f.write_text('{"x": 8089}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


def test_rejects_entry_missing_port(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"x": {"password_sha256": "aa"}}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


def test_rejects_non_int_port(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"x": {"port": "not-a-port", "password_sha256": "aa"}}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


def test_rejects_bool_port(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"x": {"port": true, "password_sha256": "aa"}}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


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


