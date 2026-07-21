"""/api/verify enforces session presence and group rules."""

from __future__ import annotations

import httpx


def _login(http: httpx.Client, username: str, password: str) -> str:
    r = http.post(
        "/api/firstfactor",
        json={
            "username": username,
            "password": password,
            "targetURL": "https://test.local/",
            "requestMethod": "GET",
            "keepMeLoggedIn": True,
        },
        headers={
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/",
            "X-Forwarded-Method": "GET",
        },
    )
    r.raise_for_status()
    return r.headers["set-cookie"].split(";", 1)[0]


def test_verify_without_cookie_returns_401(http: httpx.Client) -> None:
    r = http.get(
        "/api/verify",
        headers={
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/flash",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 401


def test_verify_with_admin_session_returns_200_and_remote_headers(http: httpx.Client) -> None:
    cookie = _login(http, "alice", "alice-password")
    r = http.get(
        "/api/verify",
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/flash",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("remote-user") == "alice"
    assert "admins" in r.headers.get("remote-groups", "")


def test_verify_admin_allowed_on_api_admin(http: httpx.Client) -> None:
    cookie = _login(http, "alice", "alice-password")
    r = http.get(
        "/api/verify",
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/api/admin/labs/pc-1/update",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert "admins" in r.headers.get("remote-groups", "")


def test_verify_without_cookie_denied_on_api_admin(http: httpx.Client) -> None:
    r = http.get(
        "/api/verify",
        headers={
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/api/admin/labs/pc-1/update",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 401
