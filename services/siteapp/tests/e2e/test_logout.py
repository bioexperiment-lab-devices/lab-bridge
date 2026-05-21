"""GET /logout returns 302 with an expiring authelia_session cookie."""

from __future__ import annotations

import httpx

from .test_whoami import _login


def _is_expired(cookie_str: str) -> bool:
    return "Max-Age=0" in cookie_str or "expires" in cookie_str.lower()


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
    assert any("authelia_session=" in c and _is_expired(c) for c in set_cookies), (
        f"authelia_session not cleared: {set_cookies}"
    )


def test_logout_also_expires_grafana_session_cookie(http: httpx.Client) -> None:
    """The navbar logout must drop Grafana too. Grafana's session cookie is
    independent of Authelia's, so without explicit expiry the user stays
    logged in to Grafana (with whatever role OIDC mapped them to) even
    after clicking 'Sign out'."""
    cookie = _login(http, "alice", "alice-password")
    r = http.get(
        "/logout",
        headers={"Cookie": cookie},
        follow_redirects=False,
    )
    set_cookies = r.headers.get_list("set-cookie")
    matches = [c for c in set_cookies if "grafana_session=" in c]
    assert matches, f"expected grafana_session in Set-Cookie; got {set_cookies}"
    assert all(_is_expired(c) for c in matches), f"grafana_session not cleared: {matches}"
    # Must target Grafana's actual cookie path so the browser matches the
    # original cookie. Grafana with serve_from_sub_path=true scopes its
    # session cookie to /grafana/.
    assert all("Path=/grafana/" in c or "path=/grafana/" in c for c in matches), (
        f"grafana_session expire missing Path=/grafana/: {matches}"
    )
