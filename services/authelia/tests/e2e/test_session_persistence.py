"""Sessions must outlive the Authelia container.

Regression test for the "logged out on every redeploy" bug: Authelia's default
session provider is in-memory, so `docker compose restart authelia` — which
scripts/deploy.sh does on every full deploy to pick up rsynced config/users
files — silently destroyed every session, remembered or not. The fix is a
Redis-backed session store (see
docs/superpowers/specs/2026-07-26-authelia-session-persistence-design.md).
"""

from __future__ import annotations

import httpx
import pytest

FORWARDED = {
    "X-Forwarded-Host": "test.local",
    "X-Forwarded-Proto": "https",
    "X-Forwarded-Uri": "/",
    "X-Forwarded-Method": "GET",
}


def _login(http: httpx.Client, *, keep_me_logged_in: bool) -> str:
    r = http.post(
        "/api/firstfactor",
        json={
            "username": "alice",
            "password": "alice-password",
            "targetURL": "/",
            "requestMethod": "GET",
            "keepMeLoggedIn": keep_me_logged_in,
        },
        headers=FORWARDED,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    cookie = r.cookies.get("authelia_session")
    assert cookie, f"no authelia_session cookie issued: {dict(r.headers)}"
    return cookie


def _verify(http: httpx.Client, cookie: str) -> int:
    return http.get(
        "/api/verify",
        headers={**FORWARDED, "Cookie": f"authelia_session={cookie}"},
    ).status_code


@pytest.mark.parametrize("keep_me_logged_in", [True, False])
def test_session_survives_authelia_restart(
    http: httpx.Client, restart_authelia, keep_me_logged_in: bool
) -> None:
    cookie = _login(http, keep_me_logged_in=keep_me_logged_in)
    assert _verify(http, cookie) == 200, "session invalid before restart"

    restart_authelia()

    assert _verify(http, cookie) == 200, (
        "session did not survive the Authelia restart — session state is not "
        "persisted (is session.redis configured?)"
    )


def test_remember_me_issues_a_persistent_cookie(http: httpx.Client) -> None:
    """`keepMeLoggedIn` must yield a cookie with an Expires far in the future.

    A session cookie (no Expires) would be dropped when the browser closes,
    which reads to a user exactly like the restart bug above.
    """
    r = http.post(
        "/api/firstfactor",
        json={
            "username": "alice",
            "password": "alice-password",
            "targetURL": "/",
            "requestMethod": "GET",
            "keepMeLoggedIn": True,
        },
        headers=FORWARDED,
    )
    assert r.status_code == 200
    set_cookie = "; ".join(
        value for key, value in r.headers.multi_items() if key.lower() == "set-cookie"
    )
    assert "expires=" in set_cookie.lower(), f"remember-me cookie is not persistent: {set_cookie}"
