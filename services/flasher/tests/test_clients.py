from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_clients_all_with_online_flags(monkeypatch, tmp_path: Path) -> None:
    roster = {
        "a": {"port": 9100, "password_sha256": ""},
        "b": {"port": 9101, "password_sha256": ""},
    }
    (tmp_path / "clients.json").write_text(json.dumps(roster), encoding="utf-8")
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "test-token")
    # Force every TCP probe to "offline" by pointing chisel host at a black hole.
    monkeypatch.setenv("FLASHER_CHISEL_HOST", "127.0.0.1")
    import importlib
    import app.main as m

    importlib.reload(m)
    with TestClient(m.app) as c:
        body = c.get("/flash/api/clients").json()
    assert {x["name"] for x in body["clients"]} == {"a", "b"}
    assert all(x["online"] is False for x in body["clients"])
    assert all("port" in x for x in body["clients"])
