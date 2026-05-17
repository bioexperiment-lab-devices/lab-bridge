"""Home page lives at / and is no longer a redirect to /docs/."""
from __future__ import annotations

import httpx


def test_root_returns_home_page(http: httpx.Client) -> None:
    r = http.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "lab-bridge" in r.text
    # Confirm the docs link is present (basic structural assertion).
    assert 'href="/docs/"' in r.text


def test_root_is_not_a_redirect(http: httpx.Client) -> None:
    r = http.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "Location" not in r.headers
