from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

SHA = "a" * 64


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch, _clients_file_default: Path):
    """Reload app.main with a TestClient; return (client, roster_file)."""
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "irrelevant-for-this-suite")
    from importlib import reload
    import app.main

    reload(app.main)
    return TestClient(app.main.app, raise_server_exceptions=False), _clients_file_default


def _write_roster(path: Path, *, name: str = "pc-1", port: int = 9001) -> None:
    path.write_text(
        '{"' + name + '": {"port": ' + str(port) + ', "password_sha256": "' + "0" * 64 + '"}}',
        encoding="utf-8",
    )


def _install_fake_request(
    monkeypatch, *, response: httpx.Response | None = None, exc: Exception | None = None
) -> list[dict]:
    """Patch httpx.AsyncClient.request; return a list that records each call."""
    calls: list[dict] = []

    async def fake_request(self, method, url, **kwargs):  # noqa: ANN001
        calls.append({"method": method, "url": url, **kwargs})
        if exc is not None:
            raise exc
        return response

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    return calls


# ---- verbatim passthrough ------------------------------------------------


@pytest.mark.parametrize(
    "status,body",
    [
        (202, {"accepted": True, "to": "2.3.0"}),
        (200, {"outcome": "noop", "reason": "already at 2.3.0"}),
        (400, {"error": "bad url", "detail": "not https"}),
        (409, {"error": "update in progress"}),
        (502, {"error": "release lookup failed", "detail": "rate limited"}),
    ],
)
def test_post_passes_agent_status_and_body_through(app_client, monkeypatch, status, body) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    _install_fake_request(monkeypatch, response=httpx.Response(status, json=body))

    r = client.post("/api/admin/labs/pc-1/update", content=b"{}")
    assert r.status_code == status
    assert r.json() == body


def test_post_forwards_to_correct_chisel_port_and_path(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9042)
    calls = _install_fake_request(
        monkeypatch, response=httpx.Response(202, json={"accepted": True, "to": "2.3.0"})
    )

    client.post("/api/admin/labs/pc-1/update", content=b"{}")
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "http://chisel:9042/agent/update"


def test_post_forwards_raw_body_unchanged(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    calls = _install_fake_request(
        monkeypatch, response=httpx.Response(202, json={"accepted": True, "to": "2.3.0"})
    )

    raw = b'{"url":"https://mirror/SerialHop-v2.3.0.exe","sha256":"' + SHA.encode() + b'"}'
    client.post("/api/admin/labs/pc-1/update", content=raw)
    assert calls[0]["content"] == raw


def test_post_empty_body_defaults_to_latest_release(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    calls = _install_fake_request(
        monkeypatch, response=httpx.Response(202, json={"accepted": True, "to": "2.3.0"})
    )

    client.post("/api/admin/labs/pc-1/update")  # no body
    assert calls[0]["content"] == b"{}"


# ---- explicit deviations -------------------------------------------------


def test_unknown_lab_returns_404_unknown_lab(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    calls = _install_fake_request(monkeypatch, response=httpx.Response(202, json={}))

    r = client.post("/api/admin/labs/ghost/update", content=b"{}")
    assert r.status_code == 404
    assert r.json() == {"error": "unknown lab", "detail": "ghost"}
    assert calls == []  # never reached the tunnel


def test_agent_404_is_clarified_as_disabled(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    _install_fake_request(monkeypatch, response=httpx.Response(404, json={"error": "not found"}))

    r = client.post("/api/admin/labs/pc-1/update", content=b"{}")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "remote update disabled"
    assert "turned off" in body["detail"].lower()
    assert body["upstream"] == {"error": "not found"}


def test_agent_unreachable_returns_503(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    _install_fake_request(monkeypatch, exc=httpx.ConnectError("tunnel down"))

    r = client.post("/api/admin/labs/pc-1/update", content=b"{}")
    assert r.status_code == 503
    assert r.json()["error"] == "agent unreachable"


def test_status_passes_body_through(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    status_body = {
        "state": "succeeded",
        "from": "2.2.0",
        "to": "2.3.0",
        "started_at": 1,
        "finished_at": 2,
    }
    calls = _install_fake_request(monkeypatch, response=httpx.Response(200, json=status_body))

    r = client.get("/api/admin/labs/pc-1/update/status")
    assert r.status_code == 200
    assert r.json() == status_body
    assert calls[0]["method"] == "GET"
    assert calls[0]["url"] == "http://chisel:9001/agent/update/status"


def test_status_unreachable_returns_503(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    _install_fake_request(monkeypatch, exc=httpx.ConnectTimeout("restarting"))

    r = client.get("/api/admin/labs/pc-1/update/status")
    assert r.status_code == 503
    assert r.json()["error"] == "agent unreachable"


def test_status_unknown_lab_returns_404(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    _install_fake_request(monkeypatch, response=httpx.Response(200, json={"state": "none"}))

    r = client.get("/api/admin/labs/ghost/update/status")
    assert r.status_code == 404
    assert r.json() == {"error": "unknown lab", "detail": "ghost"}
