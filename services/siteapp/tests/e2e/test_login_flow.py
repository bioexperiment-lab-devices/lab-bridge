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


def test_full_url_target_authenticates_and_redirect_is_path_only(http: httpx.Client) -> None:
    # Caddy's forward_auth → Authelia /api/verify redirect chain puts a *full*
    # URL into ?rd= on /login, so the login form's targetURL arrives at
    # /api/auth/firstfactor as 'https://host/path'. siteapp must strip
    # scheme+host before forwarding to Authelia — otherwise X-Forwarded-Uri
    # is a full URL and Authelia's proto+host+uri concatenation produces
    # 'https://hosthttps://host/path', which fails session-cookie-domain
    # matching and rejects the attempt with 'Authentication failed' before
    # ever checking the password.
    r = http.post(
        "/api/auth/firstfactor",
        json={
            "username": "alice",
            "password": "alice-password",
            "targetURL": "https://siteapp.local/flash",
            "keepMeLoggedIn": True,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["redirect"] == "/flash"
