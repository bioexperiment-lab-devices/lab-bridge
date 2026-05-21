"""POST /api/firstfactor returns 200 + Set-Cookie for valid credentials,
401 for invalid."""

from __future__ import annotations

import httpx


def test_firstfactor_valid_credentials_returns_200_with_cookie(http: httpx.Client) -> None:
    r = http.post(
        "/api/firstfactor",
        json={
            "username": "alice",
            "password": "alice-password",
            "targetURL": "https://test.local/flash",
            "requestMethod": "GET",
            "keepMeLoggedIn": True,
        },
        headers={
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/flash",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 200, r.text
    set_cookie = r.headers.get("set-cookie", "")
    assert "authelia_session=" in set_cookie


def test_firstfactor_invalid_credentials_returns_401(http: httpx.Client) -> None:
    r = http.post(
        "/api/firstfactor",
        json={
            "username": "alice",
            "password": "wrong",
            "targetURL": "https://test.local/flash",
            "requestMethod": "GET",
            "keepMeLoggedIn": False,
        },
        headers={
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/flash",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 401
