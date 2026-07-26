"""Sessions must outlive the Authelia container.

Regression test for the "logged out on every redeploy" bug: Authelia's default
session provider is in-memory, so `docker compose restart authelia` — which
scripts/deploy.sh does on every full deploy to pick up rsynced config/users
files — silently destroyed every session, remembered or not. The fix is a
Redis-backed session store (see
docs/superpowers/specs/2026-07-26-authelia-session-persistence-design.md).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

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
    # Read the raw header, not r.cookies: the cookie is scoped to
    # domain=test.local while the request host is 127.0.0.1, so httpx's jar
    # discards it. Same approach as test_forward_auth.py.
    set_cookie = r.headers.get("set-cookie", "")
    assert set_cookie.startswith("authelia_session="), (
        f"no authelia_session cookie issued: {set_cookie!r}"
    )
    return set_cookie.split(";", 1)[0].split("=", 1)[1]


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


def _cookie_expiry(http: httpx.Client, *, keep_me_logged_in: bool) -> datetime:
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
    assert r.status_code == 200
    # Split the attributes by hand rather than going through http.cookies:
    # SimpleCookie silently drops a whole cookie whose value contains a
    # character it dislikes, and Authelia's random session IDs are full of
    # punctuation (`!`, `#`, `%`, `^`, `$` all observed).
    header = r.headers["set-cookie"]
    expires = next(
        (
            part.split("=", 1)[1].strip()
            for part in header.split(";")
            if part.strip().lower().startswith("expires=")
        ),
        "",
    )
    assert expires, f"cookie has no Expires — it would die with the browser: {header!r}"
    return parsedate_to_datetime(expires)


def test_remember_me_extends_the_cookie_beyond_the_default_expiration(
    http: httpx.Client,
) -> None:
    """Ticking "keep me signed in" must be visible in the cookie itself.

    `remember_me_duration` is set via a key deprecated in 4.38
    (`session.remember_me_duration`, auto-mapped to `session.remember_me`);
    if that mapping ever goes away the cookie silently falls back to the
    1-hour `expiration` and users start getting logged out again.
    """
    remembered = _cookie_expiry(http, keep_me_logged_in=True)
    ordinary = _cookie_expiry(http, keep_me_logged_in=False)

    now = datetime.now(timezone.utc)
    assert remembered - now > timedelta(days=30), (
        f"remember-me cookie expires at {remembered}, well short of the "
        f"configured remember_me_duration of 90 days"
    )
    assert ordinary - now < timedelta(days=1), (
        f"non-remembered cookie expires at {ordinary}, expected the 1h "
        f"session.expiration"
    )
