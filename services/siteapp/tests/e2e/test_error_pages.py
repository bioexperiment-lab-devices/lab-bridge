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


def test_unknown_route_returns_styled_404_to_browser(http: httpx.Client) -> None:
    # Browsers hitting a path with no FastAPI route (e.g. /docsd) should land on
    # the styled 404 template instead of FastAPI's default
    # `{"detail":"Not Found"}` JSON. Triggered by the global exception handler
    # in app.main.
    r = http.get("/docsd", headers={"accept": "text/html"})
    assert r.status_code == 404
    body = r.text
    assert "lb-forbidden__card" in body
    assert "lb-forbidden__lock--404" in body
    assert "<code>/docsd</code>" in body


def test_unknown_docs_path_returns_styled_404(http: httpx.Client) -> None:
    # `/docs/{path:path}` matches but find_doc returns None — the handler must
    # raise so the global exception handler renders the styled template.
    r = http.get("/docs/khj", headers={"accept": "text/html"})
    assert r.status_code == 404
    assert "lb-forbidden__card" in r.text
    assert "<code>/docs/khj</code>" in r.text


def test_unknown_route_returns_json_to_api_clients(http: httpx.Client) -> None:
    # API clients (Accept: application/json or path under /api/) still get the
    # original FastAPI-style JSON body — a styled HTML wall would only confuse
    # scripts.
    r = http.get("/docsd", headers={"accept": "application/json"})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"detail": "Not Found"}
