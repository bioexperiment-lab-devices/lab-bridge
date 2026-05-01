from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TOKEN = "secret-token-xyz"


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", TOKEN)
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)


def _post(client: TestClient, *, token: str | None, version: str, body: bytes) -> object:
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/api/agent/upload",
        headers=headers,
        files={"binary": ("agent.exe", body, "application/octet-stream")},
        data={"version": version},
    )


def test_unauthorized_without_token(client: TestClient) -> None:
    r = _post(client, token=None, version="1.0.0", body=b"abc")
    assert r.status_code == 401


def test_unauthorized_wrong_token(client: TestClient) -> None:
    r = _post(client, token="wrong", version="1.0.0", body=b"abc")
    assert r.status_code == 401


def test_bad_version_rejected(client: TestClient) -> None:
    r = _post(client, token=TOKEN, version="not-a-semver", body=b"abc")
    assert r.status_code == 400


def test_happy_path(client: TestClient, tmp_path: Path) -> None:
    body = b"PE-bytes" * 32
    r = _post(client, token=TOKEN, version="1.2.3", body=body)
    assert r.status_code == 200
    payload = r.json()
    assert payload["version"] == "1.2.3"
    assert payload["size"] == len(body)
    assert payload["sha256"] == hashlib.sha256(body).hexdigest()

    saved = (tmp_path / "agent" / "windows" / "agent.exe").read_bytes()
    assert saved == body
    meta = json.loads((tmp_path / "agent" / "meta.json").read_text(encoding="utf-8"))
    assert meta["version"] == "1.2.3"
    assert meta["sha256"] == payload["sha256"]


def test_overwrite_replaces_atomically(client: TestClient, tmp_path: Path) -> None:
    _post(client, token=TOKEN, version="1.0.0", body=b"first")
    _post(client, token=TOKEN, version="2.0.0", body=b"second")
    saved = (tmp_path / "agent" / "windows" / "agent.exe").read_bytes()
    assert saved == b"second"
    meta = json.loads((tmp_path / "agent" / "meta.json").read_text(encoding="utf-8"))
    assert meta["version"] == "2.0.0"


def test_upload_too_large_rejected(client: TestClient, monkeypatch) -> None:
    from app import api as api_mod

    monkeypatch.setattr(api_mod, "MAX_AGENT_BYTES", 16)
    r = _post(client, token=TOKEN, version="1.0.0", body=b"x" * 100)
    assert r.status_code == 413
