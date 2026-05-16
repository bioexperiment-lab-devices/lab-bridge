from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import migrate


@pytest.fixture
def app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    (tmp_path / "clients.json").write_text("{}", encoding="utf-8")
    # Re-import main after env vars are set so load_settings + startup runs fresh.
    import importlib
    import app.main as m

    importlib.reload(m)
    return m.app


def test_app_boot_creates_database_file(app, tmp_path: Path) -> None:
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200
    assert (tmp_path / "flasher.db").exists()


def test_app_boot_sweeps_running_flashes_to_interrupted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    (tmp_path / "clients.json").write_text("{}", encoding="utf-8")

    # Build a DB with one "running" flash row, simulating a server crash.
    db_path = tmp_path / "flasher.db"
    asyncio.run(migrate(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
            "VALUES (?, 'running', 'c', 'COM3', '{}', 'firmware', 'fid', 'sha', 'name', 0, '2026-01-01T00:00:00Z')",
            ("job-abc",),
        )
        conn.commit()

    import importlib
    import app.main as m

    importlib.reload(m)

    with TestClient(m.app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT status, error_code FROM flashes WHERE id = 'job-abc'").fetchone()
    assert row[0] == "interrupted"
    assert row[1] == "interrupted"
