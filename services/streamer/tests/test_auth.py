from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth import RequiredGroupsDep, get_remote_identity


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    def me(identity=RequiredGroupsDep) -> dict[str, object]:
        return {"user": identity.user, "groups": identity.groups}

    return app


def test_identity_extracted_from_headers() -> None:
    client = TestClient(_app())
    r = client.get("/me", headers={"Remote-User": "alice", "Remote-Groups": "researchers,admins"})
    assert r.status_code == 200
    assert r.json() == {"user": "alice", "groups": ["researchers", "admins"]}


def test_missing_user_rejected() -> None:
    client = TestClient(_app())
    r = client.get("/me")
    assert r.status_code == 401


def test_user_without_required_group_rejected() -> None:
    client = TestClient(_app())
    r = client.get("/me", headers={"Remote-User": "alice", "Remote-Groups": "guests"})
    assert r.status_code == 403


def test_empty_groups_header_rejected() -> None:
    client = TestClient(_app())
    r = client.get("/me", headers={"Remote-User": "alice"})
    assert r.status_code == 403


def test_researcher_alone_allowed() -> None:
    client = TestClient(_app())
    r = client.get("/me", headers={"Remote-User": "bob", "Remote-Groups": "researchers"})
    assert r.status_code == 200
