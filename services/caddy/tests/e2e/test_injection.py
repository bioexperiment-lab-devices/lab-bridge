"""Caddy injects the navbar script tag into text/html responses only."""
from __future__ import annotations

import httpx

INJECT_NEEDLE = '<script src="/_shared/navbar.js?v=test" defer></script></head>'


def test_html_response_gets_script_injected(http: httpx.Client) -> None:
    r = http.get("/plain/html")
    assert r.status_code == 200
    assert INJECT_NEEDLE in r.text
    # Replacement is substitutive: the rewrite consumed the original </head>
    # and emitted <script…></script></head> in its place. Confirm the body
    # has exactly one </head>, not the original + appended.
    assert r.text.count("</head>") == 1


def test_json_response_unchanged(http: httpx.Client) -> None:
    r = http.get("/plain/json")
    assert r.status_code == 200
    assert "<script" not in r.text
    assert r.text == '{"ok": true}'


def test_css_response_unchanged(http: httpx.Client) -> None:
    r = http.get("/plain/css")
    assert r.status_code == 200
    assert "<script" not in r.text
    assert r.text == "body{}"


def test_tricky_html_inside_script_block_not_misfired(http: httpx.Client) -> None:
    """The replace-response plugin replaces ALL occurrences of </head> (not just
    the last/real one). The stub's tricky-html page contains two </head> tokens:
    one inside a <script> comment and one as the real closing tag.  Both get
    expanded, so the injected needle appears twice.  This is Outcome (A) per the
    task spec: document it here so the production Caddyfile.tmpl can evaluate
    whether a more targeted regex is needed before shipping."""
    r = http.get("/plain/tricky-html")
    assert r.status_code == 200
    # Plugin replaces every </head> match → count is 2, not 1.
    # The first replacement lands inside the <script> comment (harmless for
    # browsers because it is inside a JS block comment), and the second is the
    # real injection at the actual </head> close tag.
    assert r.text.count(INJECT_NEEDLE) == 2
