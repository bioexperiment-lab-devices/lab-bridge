"""flasher's SPA root container respects --nav-width so the platform navbar
can reserve space on the left."""
from __future__ import annotations

import httpx


def test_index_html_root_references_nav_width(http: httpx.Client) -> None:
    """The served index.html contains the var(--nav-width) reference so the
    platform navbar can push the SPA content to the right."""
    r = http.get("/flash/")
    assert r.status_code == 200
    # var(--nav-width) is the contract. The bundler may rewrite quote style,
    # so match the function form rather than exact whitespace.
    assert "var(--nav-width" in r.text
