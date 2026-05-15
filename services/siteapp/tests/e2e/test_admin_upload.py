"""Tests for POST /api/agent/upload — the CI agent-upload endpoint.

Bearer token is read from /run/secrets/agent_upload_token inside the
container (mounted from fixtures/agent_upload_token == 'e2e-test-token').
"""
from __future__ import annotations

import io


TOKEN = "e2e-test-token"


def test_upload_succeeds_with_valid_token(http) -> None:
    payload = b"\x00\x01\x02FAKE_EXE"
    files = {"binary": ("agent.exe", io.BytesIO(payload), "application/octet-stream")}
    data = {"version": "1.2.3"}
    r = http.post(
        "/api/agent/upload",
        headers={"Authorization": f"Bearer {TOKEN}"},
        files=files,
        data=data,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1.2.3"
    assert body["size"] == len(payload)
    # sha256 hex of payload has 64 chars
    assert len(body["sha256"]) == 64


def test_upload_rejects_invalid_version(http) -> None:
    files = {"binary": ("agent.exe", io.BytesIO(b"AAA"), "application/octet-stream")}
    data = {"version": "not.semver"}
    r = http.post(
        "/api/agent/upload",
        headers={"Authorization": f"Bearer {TOKEN}"},
        files=files,
        data=data,
    )
    assert r.status_code == 400


def test_upload_no_auth_returns_401(http) -> None:
    files = {"binary": ("agent.exe", io.BytesIO(b"AAA"), "application/octet-stream")}
    data = {"version": "1.2.3"}
    r = http.post("/api/agent/upload", files=files, data=data)
    assert r.status_code == 401


def test_upload_wrong_token_returns_401(http) -> None:
    files = {"binary": ("agent.exe", io.BytesIO(b"AAA"), "application/octet-stream")}
    data = {"version": "1.2.3"}
    r = http.post(
        "/api/agent/upload",
        headers={"Authorization": "Bearer wrong"},
        files=files,
        data=data,
    )
    assert r.status_code == 401


def test_uploaded_agent_is_downloadable(http) -> None:
    """After upload, the binary is served back via GET /download/agent/windows/agent.exe."""
    payload = b"DOWNLOADABLE_EXE_BYTES"
    files = {"binary": ("agent.exe", io.BytesIO(payload), "application/octet-stream")}
    data = {"version": "9.9.9"}
    up = http.post(
        "/api/agent/upload",
        headers={"Authorization": f"Bearer {TOKEN}"},
        files=files,
        data=data,
    )
    assert up.status_code == 200

    dl = http.get("/download/agent/windows/agent.exe")
    assert dl.status_code == 200
    assert dl.content == payload
