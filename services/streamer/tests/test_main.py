from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_ok() -> None:
    from app.main import app

    r = TestClient(app).get("/healthz")
    assert r.status_code == 200
    payload = r.json()
    assert payload["status"] == "ok"
    assert "version" in payload


def test_static_assets_mounted() -> None:
    from app.main import app

    r = TestClient(app).get("/streamer/_static/streamer.css")
    assert r.status_code == 200
    assert "lab-grid" in r.text
