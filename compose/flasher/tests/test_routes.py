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
    response = client.get("/flash/api/clients")
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
    response = client.get("/flash/api/clients")
    names = [c["name"] for c in response.json()["clients"]]
    assert names == ["alpha", "zeta"]


def test_clients_empty_when_none_online(monkeypatch, client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    monkeypatch.setattr(routes, "probe_tcp", lambda *a, **k: False)
    response = client.get("/flash/api/clients")
    assert response.status_code == 200
    assert response.json() == {"clients": []}


def test_ports_proxies_serialhop(monkeypatch, client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    body = {"ports": [{"name": "COM3", "is_usb": True}]}

    async def fake_get_ports(self) -> dict:
        return body

    monkeypatch.setattr("app.serialhop.SerialHopClient.get_ports_detailed", fake_get_ports)
    response = client.get("/flash/api/clients/lab_a/ports")
    assert response.status_code == 200
    assert response.json() == body


def test_ports_404_for_unknown_client(client: TestClient, write_roster) -> None:
    write_roster({})
    response = client.get("/flash/api/clients/nope/ports")
    assert response.status_code == 404


def test_ports_502_on_upstream_unreachable(monkeypatch, client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})

    async def fake_get_ports(self) -> dict:
        raise UpstreamUnreachable(detail="connection refused")

    monkeypatch.setattr("app.serialhop.SerialHopClient.get_ports_detailed", fake_get_ports)
    response = client.get("/flash/api/clients/lab_a/ports")
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
    response = client.get("/flash/api/clients/lab_a/ports")
    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "list ports failed"
    assert body["detail"] == "boom"


def test_post_flash_rejects_missing_client(client: TestClient, write_roster) -> None:
    write_roster({})
    response = client.post(
        "/flash/api/flash",
        json={
            "client": "nope",
            "port": "COM3",
            "firmware": ":00000001FF\n",
            "test": None,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "unknown client"


def test_post_flash_rejects_empty_firmware(client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    response = client.post(
        "/flash/api/flash",
        json={"client": "lab_a", "port": "COM3", "firmware": "", "test": None},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid request"


def test_post_flash_rejects_oversize_firmware(client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    too_big = "x" * (256 * 1024 + 1)
    response = client.post(
        "/flash/api/flash",
        json={"client": "lab_a", "port": "COM3", "firmware": too_big, "test": None},
    )
    assert response.status_code == 400


def test_post_flash_rejects_asymmetric_test_pair(client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    response = client.post(
        "/flash/api/flash",
        json={
            "client": "lab_a",
            "port": "COM3",
            "firmware": ":00000001FF\n",
            "test": {"command": "010203", "expected_response": ""},
        },
    )
    assert response.status_code == 400


def test_post_flash_rejects_odd_length_hex(client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    response = client.post(
        "/flash/api/flash",
        json={
            "client": "lab_a",
            "port": "COM3",
            "firmware": ":00000001FF\n",
            "test": {"command": "012", "expected_response": "aa"},
        },
    )
    assert response.status_code == 400


def test_post_flash_starts_background_job(monkeypatch, client: TestClient, write_roster) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    calls: list[tuple[str, dict]] = []

    async def fake_disconnect(self) -> dict:
        calls.append(("disconnect", {}))
        return {"released": 0}

    async def fake_flash(self, **kwargs: Any) -> dict:
        calls.append(("flash", kwargs))
        return {"outcome": "success", "port": kwargs["port"], "stages": {}}

    monkeypatch.setattr("app.serialhop.SerialHopClient.disconnect_devices", fake_disconnect)
    monkeypatch.setattr("app.serialhop.SerialHopClient.flash", fake_flash)

    response = client.post(
        "/flash/api/flash",
        json={
            "client": "lab_a",
            "port": "COM3",
            "firmware": ":00000001FF\n",
            "test": None,
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert job_id

    import time as _t

    polled: dict = {"status": "running"}
    for _ in range(50):
        polled = client.get(f"/flash/api/flash/{job_id}").json()
        if polled["status"] != "running":
            break
        _t.sleep(0.05)

    assert polled["status"] == "done"
    assert polled["result"]["outcome"] == "success"
    assert [c[0] for c in calls] == ["disconnect", "flash"]


def test_post_flash_forwards_skip_backup_when_true(
    monkeypatch, client: TestClient, write_roster
) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    seen: dict = {}

    async def fake_disconnect(self) -> dict:
        return {"released": 0}

    async def fake_flash(self, **kwargs: Any) -> dict:
        seen.update(kwargs)
        return {"outcome": "success", "port": kwargs["port"], "stages": {}}

    monkeypatch.setattr("app.serialhop.SerialHopClient.disconnect_devices", fake_disconnect)
    monkeypatch.setattr("app.serialhop.SerialHopClient.flash", fake_flash)

    response = client.post(
        "/flash/api/flash",
        json={
            "client": "lab_a",
            "port": "COM3",
            "firmware": ":00000001FF\n",
            "test": None,
            "skip_backup": True,
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    import time as _t

    for _ in range(50):
        polled = client.get(f"/flash/api/flash/{job_id}").json()
        if polled["status"] != "running":
            break
        _t.sleep(0.05)

    assert seen.get("skip_backup") is True


def test_post_flash_omits_skip_backup_by_default(
    monkeypatch, client: TestClient, write_roster
) -> None:
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})
    seen: dict = {}

    async def fake_disconnect(self) -> dict:
        return {"released": 0}

    async def fake_flash(self, **kwargs: Any) -> dict:
        seen.update(kwargs)
        return {"outcome": "success", "port": kwargs["port"], "stages": {}}

    monkeypatch.setattr("app.serialhop.SerialHopClient.disconnect_devices", fake_disconnect)
    monkeypatch.setattr("app.serialhop.SerialHopClient.flash", fake_flash)

    response = client.post(
        "/flash/api/flash",
        json={
            "client": "lab_a",
            "port": "COM3",
            "firmware": ":00000001FF\n",
            "test": None,
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    import time as _t

    for _ in range(50):
        polled = client.get(f"/flash/api/flash/{job_id}").json()
        if polled["status"] != "running":
            break
        _t.sleep(0.05)

    assert "skip_backup" not in seen


def test_get_flash_unknown_returns_404(client: TestClient) -> None:
    response = client.get("/flash/api/flash/does_not_exist")
    assert response.status_code == 404


def test_get_flash_current_empty_when_no_jobs(client: TestClient) -> None:
    response = client.get("/flash/api/flash/current")
    assert response.status_code == 200
    assert response.json() == {}


def test_get_flash_current_returns_running_job(
    monkeypatch, client: TestClient, write_roster
) -> None:
    """While a flash is in flight, /current surfaces it for refresh recovery."""
    import asyncio

    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})

    async def fake_disconnect(self) -> dict:
        return {"released": 0}

    # Hold the flash open so the /current query lands while the job is
    # still in the running state.
    flash_started = asyncio.Event()
    flash_release = asyncio.Event()

    async def fake_flash(self, **kwargs: Any) -> dict:
        flash_started.set()
        await flash_release.wait()
        return {"outcome": "success", "port": kwargs["port"], "stages": {}}

    monkeypatch.setattr("app.serialhop.SerialHopClient.disconnect_devices", fake_disconnect)
    monkeypatch.setattr("app.serialhop.SerialHopClient.flash", fake_flash)

    started = client.post(
        "/flash/api/flash",
        json={
            "client": "lab_a",
            "port": "COM3",
            "firmware": ":00000001FF\n",
            "test": None,
        },
    ).json()

    # Wait briefly for the background task to enter fake_flash. TestClient
    # bridges sync<->async so the task gets scheduled but we need to give
    # it a tick.
    import time as _t

    for _ in range(50):
        response = client.get("/flash/api/flash/current")
        body = response.json()
        if body.get("job_id"):
            break
        _t.sleep(0.05)

    assert body["job_id"] == started["job_id"]
    assert body["status"] == "running"


def test_get_flash_current_returns_empty_after_completion(
    monkeypatch, client: TestClient, write_roster
) -> None:
    """After a flash terminates, /current returns {} so a refresh lands on
    the wizard rather than re-mounting the result view."""
    write_roster({"lab_a": {"port": 8081, "password_sha256": "aa"}})

    async def fake_disconnect(self) -> dict:
        return {"released": 0}

    async def fake_flash(self, **kwargs: Any) -> dict:
        return {"outcome": "success", "port": kwargs["port"], "stages": {}}

    monkeypatch.setattr("app.serialhop.SerialHopClient.disconnect_devices", fake_disconnect)
    monkeypatch.setattr("app.serialhop.SerialHopClient.flash", fake_flash)

    started = client.post(
        "/flash/api/flash",
        json={
            "client": "lab_a",
            "port": "COM3",
            "firmware": ":00000001FF\n",
            "test": None,
        },
    ).json()

    import time as _t

    # Wait for the job to terminate.
    for _ in range(50):
        polled = client.get(f"/flash/api/flash/{started['job_id']}").json()
        if polled["status"] != "running":
            break
        _t.sleep(0.05)
    assert polled["status"] == "done"

    # Now /current must NOT surface the terminated job.
    response = client.get("/flash/api/flash/current")
    assert response.status_code == 200
    assert response.json() == {}
