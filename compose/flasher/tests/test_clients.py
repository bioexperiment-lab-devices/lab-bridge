from __future__ import annotations

from pathlib import Path

import pytest

from app.clients import load_roster


def test_happy_path(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text(
        '{"khamit_desktop": {"port": 8089, "password_sha256": "aa"},'
        ' "another_lab": {"port": 8090, "password_sha256": "bb"}}',
        encoding="utf-8",
    )

    assert load_roster(f) == {
        "khamit_desktop": {"port": 8089},
        "another_lab": {"port": 8090},
    }


def test_empty_roster(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text("{}", encoding="utf-8")
    assert load_roster(f) == {}


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        load_roster(tmp_path / "does_not_exist.json")


def test_malformed_json_raises(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_roster(f)


def test_top_level_not_object_raises(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text("[1,2,3]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        load_roster(f)


def test_rejects_non_int_port(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"x": {"port": "8089", "password_sha256": "aa"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="port must be int"):
        load_roster(f)


def test_rejects_bool_port(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"x": {"port": true, "password_sha256": "aa"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="port must be int"):
        load_roster(f)
