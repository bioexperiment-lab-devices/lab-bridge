"""siteapp's base.html exposes the --nav-width hook for the platform navbar
and no longer carries the legacy lab-bridge topbar (the sidebar replaces it)."""

from __future__ import annotations

import httpx


def test_base_html_exposes_nav_width_padding(http: httpx.Client) -> None:
    """Either inline style on body/main OR a class with the padding rule
    that references --nav-width."""
    r = http.get("/docs/")
    assert r.status_code == 200
    assert "var(--nav-width" in r.text


def test_legacy_topbar_is_removed(http: httpx.Client) -> None:
    r = http.get("/docs/")
    assert r.status_code == 200
    assert '<header class="topbar"' not in r.text
