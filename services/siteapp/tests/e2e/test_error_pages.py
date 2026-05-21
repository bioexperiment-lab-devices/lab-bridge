"""GET /_errors/403 and /_errors/404 render templates extending base.html."""

from __future__ import annotations

import httpx


def test_error_403_renders_with_base_template(http: httpx.Client) -> None:
    r = http.get("/_errors/403")
    assert r.status_code == 200
    body = r.text
    # Base template marker.
    assert "/_static/site.css" in body or "/_static/tokens.css" in body
    # New design markers.
    assert "Error 403 · Forbidden" in body          # mono eyebrow
    assert "lb-forbidden__card" in body              # card shell
    assert "lb-forbidden__lock" in body              # warning lock badge
    assert "lb-forbidden__meta" in body              # attempted-path meta block
    assert "You don't have access to this page" in body  # title copy


def test_error_403_renders_attempted_path_from_query(http: httpx.Client) -> None:
    r = http.get("/_errors/403?path=/admin/users")
    assert r.status_code == 200
    assert "<code>/admin/users</code>" in r.text


def test_error_403_falls_back_to_request_path_when_query_missing(http: httpx.Client) -> None:
    r = http.get("/_errors/403")
    assert r.status_code == 200
    # Fallback path used by direct hits (no Caddy in front).
    assert "<code>/_errors/403</code>" in r.text


def test_error_404_renders_with_base_template(http: httpx.Client) -> None:
    r = http.get("/_errors/404")
    assert r.status_code == 200
    body = r.text
    assert "404" in body
    assert "/_static/site.css" in body or "/_static/tokens.css" in body
