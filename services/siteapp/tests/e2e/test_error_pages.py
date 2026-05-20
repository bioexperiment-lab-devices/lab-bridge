"""GET /_errors/403 and /_errors/404 render templates extending base.html."""

from __future__ import annotations

import httpx


def test_error_403_renders_with_base_template(http: httpx.Client) -> None:
    r = http.get("/_errors/403")
    assert r.status_code == 200
    body = r.text
    assert "403" in body
    # Base template marker.
    assert "/_static/site.css" in body or "/_static/tokens.css" in body


def test_error_404_renders_with_base_template(http: httpx.Client) -> None:
    r = http.get("/_errors/404")
    assert r.status_code == 200
    body = r.text
    assert "404" in body
    assert "/_static/site.css" in body or "/_static/tokens.css" in body
