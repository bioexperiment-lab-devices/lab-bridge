from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.roster import load_roster


def _write(tmp_path: Path, content: object) -> Path:
    p = tmp_path / "clients.json"
    p.write_text(json.dumps(content), encoding="utf-8")
    return p


def test_load_roster_returns_name_to_port(tmp_path: Path) -> None:
    p = _write(tmp_path, {"alice": {"port": 8089}, "bob": {"port": 8090}})
    assert load_roster(p) == {"alice": 8089, "bob": 8090}


def test_load_roster_ignores_other_entry_fields(tmp_path: Path) -> None:
    p = _write(tmp_path, {"alice": {"port": 8089, "password_sha256": "abc"}})
    assert load_roster(p) == {"alice": 8089}


def test_load_roster_rejects_non_object_root(tmp_path: Path) -> None:
    p = _write(tmp_path, [{"alice": 1}])
    with pytest.raises(ValueError, match="JSON object"):
        load_roster(p)


def test_load_roster_rejects_non_object_entry(tmp_path: Path) -> None:
    p = _write(tmp_path, {"alice": 8089})
    with pytest.raises(ValueError, match="must be object"):
        load_roster(p)


def test_load_roster_rejects_bool_port(tmp_path: Path) -> None:
    p = _write(tmp_path, {"alice": {"port": True}})
    with pytest.raises(ValueError, match="port must be int"):
        load_roster(p)


def test_load_roster_rejects_str_port(tmp_path: Path) -> None:
    p = _write(tmp_path, {"alice": {"port": "8089"}})
    with pytest.raises(ValueError, match="port must be int"):
        load_roster(p)


def test_load_roster_missing_file_raises_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        load_roster(tmp_path / "nope.json")
