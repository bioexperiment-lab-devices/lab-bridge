"""GET and POST /logout return 302 with an expiring authelia_session cookie."""

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
    # session cookie to `/grafana` (no trailing slash) — using `/grafana/`
    # creates a new empty cookie at a different path while the original
    # at /grafana lives on, and the user stays logged in.
    assert all("path=/grafana;" in c.lower() for c in matches), (
        f"grafana_session expire must use Path=/grafana (no trailing slash): {matches}"
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


def test_logout_cleared_cookies_carry_secure(http: httpx.Client) -> None:
    """All three logout-cleared cookies must include Secure so they're never
    re-sent over plaintext. Audit finding 2.5."""
    cookie = _login(http, "alice", "alice-password")
    r = http.get(
        "/logout",
        headers={"Cookie": cookie},
        follow_redirects=False,
    )
    set_cookies = r.headers.get_list("set-cookie")
    for name in ("authelia_session", "grafana_session", "grafana_session_expiry"):
        matches = [c for c in set_cookies if c.startswith(f"{name}=")]
        assert matches, f"missing clear-line for {name}: {set_cookies}"
        for c in matches:
            assert "Secure" in c, f"{name} clear-line missing Secure: {c}"


def test_logout_invalidates_authelia_session_server_side(
    http: httpx.Client,
) -> None:
    """The cookie issued by /api/auth/firstfactor must not work against
    /api/auth/whoami after /logout. Without server-side invalidation,
    Authelia's session record persists and the cookie remains valid even
    though the client-side clear succeeded. Audit findings 2.1, 2.2."""
    cookie = _login(http, "alice", "alice-password")
    # Sanity: the cookie works pre-logout.
    r = http.get("/api/auth/whoami", headers={"Cookie": cookie})
    assert r.status_code == 200
    assert r.json()["user"] == "alice", f"pre-logout whoami unexpected: {r.json()}"
    # Log out via GET (covers 2.1) — POST flavour covered by 2.2 in the
    # audit harness.
    http.get("/logout", headers={"Cookie": cookie}, follow_redirects=False)
    # Replay the *original* cookie. It must not authenticate any more.
    r = http.get("/api/auth/whoami", headers={"Cookie": cookie})
    assert r.status_code == 200
    assert r.json()["user"] is None, f"replay after logout should not authenticate; got {r.json()}"
