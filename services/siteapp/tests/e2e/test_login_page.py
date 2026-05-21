"""GET /login renders the form and preserves ?rd= in the markup."""

from __future__ import annotations

import httpx


def test_login_page_returns_200_and_has_form(http: httpx.Client) -> None:
    r = http.get("/login", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert '<form id="login-form"' in body
    assert 'name="username"' in body
    assert 'name="password"' in body


def test_login_page_includes_navbar_marker(http: httpx.Client) -> None:
    # The Caddy navbar injection happens at the edge; in the e2e harness siteapp
    # is hit directly so we instead verify that base.html is the host template
    # (presence of the /_static asset references that base.html owns).
    r = http.get("/login")
    body = r.text
    assert "/_static/site.css" in body or "/_static/tokens.css" in body


def test_login_page_carries_rd_into_inline_script(http: httpx.Client) -> None:
    r = http.get("/login?rd=/flash")
    assert "/flash" in r.text
