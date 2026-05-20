"""GET /api/auth/whoami reflects session state."""

from __future__ import annotations

import httpx


def _login(http: httpx.Client, username: str, password: str) -> str:
    r = http.post(
        "/api/auth/firstfactor",
        json={
            "username": username,
            "password": password,
            "targetURL": "/",
            "keepMeLoggedIn": True,
        },
    )
    r.raise_for_status()
    return r.headers.get_list("set-cookie")[0].split(";", 1)[0]


def test_whoami_returns_null_when_anonymous(http: httpx.Client) -> None:
    r = http.get("/api/auth/whoami")
    assert r.status_code == 200
    assert r.json() == {"user": None}


def test_whoami_returns_user_and_groups_when_authenticated(http: httpx.Client) -> None:
    cookie = _login(http, "alice", "alice-password")
    r = http.get("/api/auth/whoami", headers={"Cookie": cookie})
    assert r.status_code == 200
    body = r.json()
    assert body["user"] == "alice"
    assert "admins" in body["groups"]
