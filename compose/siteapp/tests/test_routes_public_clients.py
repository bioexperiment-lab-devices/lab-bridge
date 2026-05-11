from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.public_clients import (
    _load_roster,
    _parse_bearer,
    _verify,
)


# ----- _parse_bearer ------------------------------------------------------

def test_parse_bearer_returns_token() -> None:
    assert _parse_bearer("Bearer abc123") == "abc123"


def test_parse_bearer_is_case_insensitive_for_scheme() -> None:
    assert _parse_bearer("bearer abc123") == "abc123"
    assert _parse_bearer("BEARER abc123") == "abc123"


def test_parse_bearer_strips_trailing_whitespace() -> None:
    assert _parse_bearer("Bearer abc123   ") == "abc123"


def test_parse_bearer_none_returns_empty() -> None:
    assert _parse_bearer(None) == ""


def test_parse_bearer_wrong_scheme_returns_empty() -> None:
    assert _parse_bearer("Basic abc123") == ""


def test_parse_bearer_empty_string_returns_empty() -> None:
    assert _parse_bearer("") == ""


# ----- _load_roster -------------------------------------------------------

def test_load_roster_returns_raw_dict(tmp_path: Path) -> None:
    f = tmp_path / "r.json"
    f.write_text('{"a": {"port": 1, "password_sha256": "aa"}}', encoding="utf-8")
    assert _load_roster(f) == {"a": {"port": 1, "password_sha256": "aa"}}


def test_load_roster_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        _load_roster(tmp_path / "nope.json")


def test_load_roster_malformed_raises(tmp_path: Path) -> None:
    f = tmp_path / "r.json"
    f.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        _load_roster(f)


def test_load_roster_non_object_raises(tmp_path: Path) -> None:
    f = tmp_path / "r.json"
    f.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        _load_roster(f)


# ----- _verify ------------------------------------------------------------

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_verify_hit_returns_entry() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("alice", "s3cret", roster) == roster["alice"]


def test_verify_wrong_password_returns_none() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("alice", "wrong", roster) is None


def test_verify_unknown_user_returns_none() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("eve", "anything", roster) is None


def test_verify_empty_bearer_returns_none() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("alice", "", roster) is None


def test_verify_entry_missing_hash_returns_none() -> None:
    # Malformed roster: entry has no password_sha256. Should fail closed.
    roster = {"alice": {"port": 8089}}
    assert _verify("alice", "anything", roster) is None


def test_verify_entry_malformed_hash_returns_none() -> None:
    # Non-hex hash. Should fail closed without raising.
    roster = {"alice": {"port": 8089, "password_sha256": "not-hex!"}}
    assert _verify("alice", "anything", roster) is None


# ----- _probe_tunnel ------------------------------------------------------

import socket
from unittest.mock import patch, MagicMock


def test_probe_tunnel_open_port_returns_true() -> None:
    from app.public_clients import _probe_tunnel

    mock_sock = MagicMock()
    mock_sock.__enter__ = MagicMock(return_value=mock_sock)
    mock_sock.__exit__ = MagicMock(return_value=False)

    with patch("app.public_clients.socket.create_connection", return_value=mock_sock) as m:
        assert _probe_tunnel(8089) is True
    m.assert_called_once()
    args, kwargs = m.call_args
    assert args[0] == ("chisel", 8089)


def test_probe_tunnel_closed_port_returns_false() -> None:
    from app.public_clients import _probe_tunnel

    with patch("app.public_clients.socket.create_connection", side_effect=OSError("refused")):
        assert _probe_tunnel(8089) is False


def test_probe_tunnel_timeout_returns_false() -> None:
    from app.public_clients import _probe_tunnel

    with patch("app.public_clients.socket.create_connection", side_effect=socket.timeout):
        assert _probe_tunnel(8089) is False


# ----- /api/public/clients/{username} -------------------------------------

import hashlib as _hashlib_for_routes
from fastapi.testclient import TestClient


PASSWORD = "ccTMYfkmJmIQCg-ApvdjV5l4IBqZT0dD"
USERNAME = "khamit_desktop"


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch, _clients_file_default: Path):
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "irrelevant-for-this-suite")
    from importlib import reload
    import app.main
    reload(app.main)
    # raise_server_exceptions=False so 500-path tests see HTTP 500
    return TestClient(app.main.app, raise_server_exceptions=False), _clients_file_default


def _write_roster(path: Path, *, username: str = USERNAME, password: str = PASSWORD, port: int = 8089) -> None:
    pwhash = _hashlib_for_routes.sha256(password.encode("utf-8")).hexdigest()
    path.write_text(
        '{"' + username + '": {"port": ' + str(port) + ', "password_sha256": "' + pwhash + '"}}',
        encoding="utf-8",
    )


def test_public_clients_happy_path_returns_port_and_connected(app_client, monkeypatch) -> None:
    client, roster_file = app_client
    _write_roster(roster_file, port=8089)
    monkeypatch.setattr("app.public_clients._probe_tunnel", lambda port: True)

    r = client.get(
        f"/api/public/clients/{USERNAME}",
        headers={"Authorization": f"Bearer {PASSWORD}"},
    )
    assert r.status_code == 200
    assert r.json() == {"port": 8089, "connected": True}


def test_public_clients_returns_connected_false_when_probe_fails(app_client, monkeypatch) -> None:
    client, roster_file = app_client
    _write_roster(roster_file, port=8089)
    monkeypatch.setattr("app.public_clients._probe_tunnel", lambda port: False)

    r = client.get(
        f"/api/public/clients/{USERNAME}",
        headers={"Authorization": f"Bearer {PASSWORD}"},
    )
    assert r.status_code == 200
    assert r.json() == {"port": 8089, "connected": False}


def test_public_clients_401_responses_are_byte_identical(app_client) -> None:
    client, roster_file = app_client
    _write_roster(roster_file)

    cases = {
        "wrong_token": (USERNAME, {"Authorization": "Bearer wrong-password-zzz"}),
        "unknown_user": ("does-not-exist", {"Authorization": f"Bearer {PASSWORD}"}),
        "missing_header": (USERNAME, {}),
        "wrong_scheme": (USERNAME, {"Authorization": f"Basic {PASSWORD}"}),
    }

    results = {}
    for name, (username, headers) in cases.items():
        r = client.get(f"/api/public/clients/{username}", headers=headers)
        body = r.content
        status = r.status_code
        ignored = {"date", "server", "content-length"}
        hdrs = {k.lower(): v for k, v in r.headers.items() if k.lower() not in ignored}
        results[name] = (status, body, hdrs)

    statuses = {v[0] for v in results.values()}
    bodies = {v[1] for v in results.values()}
    headerses = [v[2] for v in results.values()]
    assert statuses == {401}, f"non-401 in {results}"
    assert len(bodies) == 1, f"non-identical bodies: {bodies}"
    assert all(h == headerses[0] for h in headerses), f"non-identical headers: {headerses}"


def test_public_clients_missing_roster_returns_500(app_client) -> None:
    client, roster_file = app_client
    roster_file.unlink()
    r = client.get(
        f"/api/public/clients/{USERNAME}",
        headers={"Authorization": f"Bearer {PASSWORD}"},
    )
    assert r.status_code == 500


def test_public_clients_malformed_roster_returns_500(app_client) -> None:
    client, roster_file = app_client
    roster_file.write_text("not-json", encoding="utf-8")
    r = client.get(
        f"/api/public/clients/{USERNAME}",
        headers={"Authorization": f"Bearer {PASSWORD}"},
    )
    assert r.status_code == 500


# ----- /api/public/health -------------------------------------------------

import httpx


class _FakeResp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            req = httpx.Request("GET", "http://chisel:7000/health")
            raise httpx.HTTPStatusError(
                f"http {self.status_code}", request=req, response=httpx.Response(self.status_code, request=req)
            )


def test_health_ok_when_chisel_returns_200(app_client, monkeypatch) -> None:
    client, _ = app_client
    monkeypatch.setattr("app.public_clients.httpx.get", lambda *a, **kw: _FakeResp(200))

    r = client.get("/api/public/health")
    assert r.status_code == 200
    assert r.json() == {"chisel": "ok"}


def test_health_down_when_chisel_returns_5xx(app_client, monkeypatch) -> None:
    client, _ = app_client
    monkeypatch.setattr("app.public_clients.httpx.get", lambda *a, **kw: _FakeResp(502))

    r = client.get("/api/public/health")
    assert r.status_code == 200
    body = r.json()
    assert body["chisel"] == "down"
    assert body["error"] == "http 502"


def test_health_down_on_timeout(app_client, monkeypatch) -> None:
    def _raise(*a, **kw):
        raise httpx.TimeoutException("slow")

    client, _ = app_client
    monkeypatch.setattr("app.public_clients.httpx.get", _raise)

    r = client.get("/api/public/health")
    assert r.status_code == 200
    body = r.json()
    assert body["chisel"] == "down"
    assert body["error"] == "timeout"


def test_health_down_on_connect_error(app_client, monkeypatch) -> None:
    def _raise(*a, **kw):
        raise httpx.ConnectError("refused")

    client, _ = app_client
    monkeypatch.setattr("app.public_clients.httpx.get", _raise)

    r = client.get("/api/public/health")
    assert r.status_code == 200
    body = r.json()
    assert body["chisel"] == "down"
    assert body["error"] == "connecterror"


def test_health_route_does_not_require_auth(app_client) -> None:
    # No mocking — let the real httpx call fail (chisel is not running
    # in the unit-test process). What we're asserting is that the lack
    # of an Authorization header does NOT short-circuit the request.
    client, _ = app_client
    r = client.get("/api/public/health")
    assert r.status_code == 200
    # Either "ok" or "down" is fine; we're checking the route is reachable
    # without credentials.
    assert r.json()["chisel"] in {"ok", "down"}
