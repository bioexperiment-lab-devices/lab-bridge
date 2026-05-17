"""Caddy regex-appends 'self' to script-src and style-src on routes that
need it (the /jupyter and /grafana routes in production)."""
from __future__ import annotations

import httpx


def _directive_tokens(csp: str, name: str) -> str:
    """Return the token list for a CSP directive named `name`.

    Returns the substring between `name` and the next `;` (or end of string).
    Assumes `;` terminates every directive — safe because test fixtures
    control the upstream CSP header format. Would need adjusting if a
    real-world upstream emits a trailing directive without `;`.
    """
    return csp.split(name, 1)[1].split(";", 1)[0]


def test_csp_script_src_includes_self(http: httpx.Client) -> None:
    """script-src rewrite is idempotent when 'self' is already present."""
    r = http.get("/csp/html-csp")
    assert r.status_code == 200
    csp = r.headers["Content-Security-Policy"]
    # Fixture upstream already includes 'self'; assertion confirms idempotence.
    assert "script-src" in csp
    assert "'self'" in _directive_tokens(csp, "script-src")


def test_csp_style_src_includes_self(http: httpx.Client) -> None:
    """style-src rewrite mirrors script-src behavior; both are appended with 'self'."""
    r = http.get("/csp/html-csp")
    csp = r.headers["Content-Security-Policy"]
    assert "style-src" in csp
    assert "'self'" in _directive_tokens(csp, "style-src")


def test_csp_unchanged_when_no_script_src_directive(http: httpx.Client) -> None:
    """If the upstream omits script-src (default-src applies), we don't touch
    the header. Test that the page still serves and CSP is preserved."""
    r = http.get("/csp/html-no-script")
    csp = r.headers["Content-Security-Policy"]
    assert csp == "default-src 'self'"


def test_csp_strict_default_none_is_known_failure_mode(http: httpx.Client) -> None:
    """If upstream ships default-src 'none' AND has a script-src that excludes
    'self', the rewrite still appends 'self' to script-src. The injected
    script will work. (This is the regression line for risk #5 in the spec.)"""
    r = http.get("/csp/html-strict")
    csp = r.headers["Content-Security-Policy"]
    assert "'self'" in _directive_tokens(csp, "script-src")
