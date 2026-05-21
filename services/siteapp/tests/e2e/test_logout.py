"""GET and POST /logout return 302 with an expiring authelia_session cookie."""

from __future__ import annotations

import httpx

from .test_whoami import _login


def test_logout_returns_302_and_expires_cookie(http: httpx.Client) -> None:
    cookie = _login(http, "alice", "alice-password")
    r = http.get(
        "/logout",
        headers={"Cookie": cookie},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/"
    set_cookies = r.headers.get_list("set-cookie")
    assert any(
        "authelia_session=" in c and ("Max-Age=0" in c or "expires" in c.lower())
        for c in set_cookies
    )


def test_logout_accepts_post_and_expires_cookie(http: httpx.Client) -> None:
    cookie = _login(http, "alice", "alice-password")
    r = http.post(
        "/logout",
        headers={"Cookie": cookie},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/"
    set_cookies = r.headers.get_list("set-cookie")
    assert any(
        "authelia_session=" in c and ("Max-Age=0" in c or "expires" in c.lower())
        for c in set_cookies
    )
