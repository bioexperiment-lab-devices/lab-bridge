from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch) -> TestClient:
    """Boot the FastAPI app with the standard test env."""
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "irrelevant-for-this-suite")
    # SITEAPP_CHISEL_LISTEN_PORT + SITEAPP_CLIENTS_FILE come from autouse fixtures.
    from importlib import reload

    import app.main
    reload(app.main)
    return TestClient(app.main.app)


def test_server_info_returns_expected_shape(app_client: TestClient) -> None:
    r = app_client.get("/api/public/server-info")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "chisel": {"listen_port": 8080},
        "loki": {"push_url": "http://127.0.0.1:3100/loki/api/v1/push"},
        "forward_tunnels": [
            {"name": "loki", "local": "127.0.0.1:3100", "remote": "loki:3100"}
        ],
    }


def test_server_info_reflects_configured_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The listen_port in the response tracks SITEAPP_CHISEL_LISTEN_PORT, not a constant."""
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_CHISEL_LISTEN_PORT", "9090")
    from importlib import reload

    import app.main
    reload(app.main)
    client = TestClient(app.main.app)

    r = client.get("/api/public/server-info")
    assert r.status_code == 200
    assert r.json()["chisel"] == {"listen_port": 9090}


def test_server_info_requires_no_auth(app_client: TestClient) -> None:
    """Regression guard: an accidental Depends(...) on the route would break the
    'agent can fetch this before holding any credential' guarantee."""
    r = app_client.get("/api/public/server-info")  # no Authorization header
    assert r.status_code == 200
