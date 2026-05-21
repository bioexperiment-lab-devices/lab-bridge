"""POST /api/auth/firstfactor authenticates against Authelia and pipes the
Set-Cookie back."""

from __future__ import annotations

import httpx


def test_valid_login_returns_200_and_sets_authelia_cookie(http: httpx.Client) -> None:
    r = http.post(
        "/api/auth/firstfactor",
        json={
            "username": "alice",
            "password": "alice-password",
            "targetURL": "/flash",
            "keepMeLoggedIn": True,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["redirect"] == "/flash"
    set_cookies = r.headers.get_list("set-cookie")
    assert any("authelia_session=" in c for c in set_cookies)


def test_invalid_password_returns_401(http: httpx.Client) -> None:
    r = http.post(
        "/api/auth/firstfactor",
        json={
            "username": "alice",
            "password": "wrong",
            "targetURL": "/flash",
            "keepMeLoggedIn": False,
        },
    )
    assert r.status_code == 401
