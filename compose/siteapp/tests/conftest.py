from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def site_data(tmp_path: Path) -> Path:
    """Fresh, empty site_data/ tree for a single test."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "agent" / "windows").mkdir(parents=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _clients_file_default(tmp_path: Path, monkeypatch) -> Path:
    """Set SITEAPP_CLIENTS_FILE to a fresh empty roster for every test.

    Tests that need actual roster content can request the `clients_file`
    fixture (in test_routes_api.py) and write to it directly. This
    autouse fixture only ensures load_settings() doesn't blow up when
    individual tests don't care about the clients endpoint.
    """
    p = tmp_path / "clients.json"
    p.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SITEAPP_CLIENTS_FILE", str(p))
    return p
