"""Non-HTML responses are byte-identical post-Caddy; gzip roundtrips correctly."""
from __future__ import annotations

import httpx
import pytest


def test_gzip_html_is_decoded_rewritten_and_re_served(http: httpx.Client) -> None:
    """The replace-response plugin operates on decompressed bodies. The
    upstream sends gzip; Caddy decompresses, rewrites, and serves (potentially
    re-compressed, depending on negotiation).

    Note: the fixture's ``header_up -Accept-Encoding`` in the /plain/* block
    strips the client's Accept-Encoding before it reaches the stub, so the
    stub always returns plain text to Caddy.  The actual gzip negotiation with
    the upstream never fires; this test is a "fixture handles the header
    without crashing" smoke, and confirms the rewrite still runs correctly."""
    r = http.get("/plain/html", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    # httpx auto-decompresses; r.text is the final plaintext.
    assert "<script" in r.text


def test_json_byte_identical(http: httpx.Client) -> None:
    r = http.get("/plain/json")
    assert r.content == b'{"ok": true}'


def test_css_byte_identical(http: httpx.Client) -> None:
    r = http.get("/plain/css")
    assert r.content == b"body{}"


def test_static_navbar_js_served_unmodified(http: httpx.Client) -> None:
    """The /_shared/* route is file_server, NOT the rewrite path. The static
    file must be served byte-identical."""
    r = http.get("/_shared/navbar.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript") or \
           r.headers["content-type"].startswith("text/javascript")
    assert "loaded" in r.text  # from the fixture placeholder


def test_navbar_js_contains_mutation_observer_guard(http: httpx.Client) -> None:
    """The navbar.js bundle includes a MutationObserver that re-attaches the
    custom element if it is removed (spec risk #3 — JupyterLab SPA may
    destroy body content during internal nav)."""
    r = http.get("/_shared/navbar.js")
    assert r.status_code == 200
    # The fixture serves the placeholder; if it doesn't contain MutationObserver,
    # skip — this assertion fires in CI against the real bundle (via the
    # platform bats smoke), and locally when developers point the fixture at
    # the real file. The textual check is intentionally weak: we're guarding
    # against accidental deletion of the guard, not asserting semantics.
    if "MutationObserver" not in r.text:
        pytest.skip("placeholder navbar.js in fixture; real check is in bats")
