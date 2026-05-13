from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import routes
from app.serialhop import UpstreamErrorResponse, UpstreamUnreachable


@pytest.fixture
def client() -> TestClient:
    """Reload app.main inside the fixture so it picks up per-test env vars.

    Without the reload, app.main's module-level `settings = load_settings()`
    would run at collection time — before the autouse monkeypatch fixtures
    that set FLASHER_CLIENTS_FILE per test.
    """
    import app.main

    importlib.reload(app.main)
    return TestClient(app.main.app)


@pytest.fixture
def write_roster(clients_file: Path):
    def _write(data: dict[str, dict[str, Any]]) -> None:
        import json

        clients_file.write_text(json.dumps(data), encoding="utf-8")

    return _write


def test_clients_returns_only_online(monkeypatch, client: TestClient, write_roster) -> None:
    write_roster(
        {
            "lab_a": {"port": 8081, "password_sha256": "aa"},
            "lab_b": {"port": 8082, "password_sha256": "bb"},
        }
    )

    def fake_probe(host: str, port: int) -> bool:
        return port == 8081  # only lab_a is online

    monkeypatch.setattr(routes, "probe_tcp", fake_probe)
    response = client.get("/api/clients")
    assert response.status_code == 200
    assert response.json() == {"clients": [{"name": "lab_a", "port": 8081}]}


def test_clients_sorted_by_name(monkeypatch, client: TestClient, write_roster) -> None:
    write_roster(
        {
            "zeta": {"port": 8091, "password_sha256": "aa"},
            "alpha": {"port": 8092, "password_sha256": "bb"},
        }
    )
    monkeypatch.setattr(routes, "probe_tcp", lambda *a, **k: True)
    response = client.get("/api/clients")
    names = [c["name"] for c in response.json()["clients"]]
    assert names == ["alpha", "zeta"]


def test_clients_empty_when_none_online(monkeypatch, client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    monkeypatch.setattr(routes, "probe_tcp", lambda *a, **k: False)
    response = client.get("/api/clients")
    assert response.status_code == 200
    assert response.json() == {"clients": []}


def test_ports_proxies_serialhop(monkeypatch, client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    body = {"ports": [{"name": "COM3", "is_usb": True}]}

    async def fake_get_ports(self) -> dict:
        return body

    monkeypatch.setattr("app.serialhop.SerialHopClient.get_ports_detailed", fake_get_ports)
    response = client.get("/api/clients/lab_a/ports")
    assert response.status_code == 200
    assert response.json() == body


def test_ports_404_for_unknown_client(client: TestClient, write_roster) -> None:
    write_roster({})
    response = client.get("/api/clients/nope/ports")
    assert response.status_code == 404


def test_ports_502_on_upstream_unreachable(monkeypatch, client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})

    async def fake_get_ports(self) -> dict:
        raise UpstreamUnreachable(detail="connection refused")

    monkeypatch.setattr("app.serialhop.SerialHopClient.get_ports_detailed", fake_get_ports)
    response = client.get("/api/clients/lab_a/ports")
    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "upstream unreachable"
    assert "connection refused" in body["detail"]


def test_ports_relays_serialhop_error_envelope(
    monkeypatch, client: TestClient, write_roster
) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})

    async def fake_get_ports(self) -> dict:
        raise UpstreamErrorResponse(status_code=500, error_code="list ports failed", detail="boom")

    monkeypatch.setattr("app.serialhop.SerialHopClient.get_ports_detailed", fake_get_ports)
    response = client.get("/api/clients/lab_a/ports")
    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "list ports failed"
    assert body["detail"] == "boom"
