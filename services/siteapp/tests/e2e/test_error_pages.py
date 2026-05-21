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
    assert "Error 403 · Forbidden" in body  # mono eyebrow
    assert "lb-forbidden__card" in body  # card shell
    assert "lb-forbidden__lock" in body  # warning lock badge
    assert "lb-forbidden__meta" in body  # attempted-path meta block
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


def test_error_403_escapes_html_in_attempted_path(http: httpx.Client) -> None:
    # Guards against an accidental disable of Jinja autoescape in a future
    # refactor of templates.py. The query is rendered inside a <code> chip.
    r = http.get("/_errors/403?path=</code><script>x</script>")
    assert r.status_code == 200
    assert "<script>x</script>" not in r.text
    assert "&lt;/code&gt;" in r.text
    assert "&lt;script&gt;" in r.text


def test_error_404_renders_with_base_template(http: httpx.Client) -> None:
    r = http.get("/_errors/404")
    assert r.status_code == 200
    body = r.text
    assert "/_static/site.css" in body or "/_static/tokens.css" in body
    assert "Error 404 · Not found" in body
    assert "lb-forbidden__card" in body
    assert "lb-forbidden__lock--404" in body  # neutral magnifier modifier
    assert "lb-forbidden__meta" in body
    assert "Page not found" in body  # title copy


def test_error_404_renders_attempted_path_from_query(http: httpx.Client) -> None:
    r = http.get("/_errors/404?path=/lab/benchz-42")
    assert r.status_code == 200
    assert "<code>/lab/benchz-42</code>" in r.text


def test_error_404_falls_back_to_request_path_when_query_missing(http: httpx.Client) -> None:
    r = http.get("/_errors/404")
    assert r.status_code == 200
    assert "<code>/_errors/404</code>" in r.text


def test_error_404_escapes_html_in_attempted_path(http: httpx.Client) -> None:
    # Symmetry with the 403 autoescape test — both share the same _attempted_path
    # helper and the same Jinja rendering pipeline, so a regression would show
    # up identically on both routes.
    r = http.get("/_errors/404?path=</code><script>x</script>")
    assert r.status_code == 200
    assert "<script>x</script>" not in r.text
    assert "&lt;/code&gt;" in r.text
    assert "&lt;script&gt;" in r.text
