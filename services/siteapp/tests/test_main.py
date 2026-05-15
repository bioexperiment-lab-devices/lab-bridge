from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "test-token")
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)


def test_healthz(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
