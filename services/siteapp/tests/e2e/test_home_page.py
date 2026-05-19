"""End-to-end coverage for the redesigned Home page."""

from __future__ import annotations

import httpx


def test_root_returns_home_page(http: httpx.Client) -> None:
    r = http.get("/", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert "lab-bridge" in body
    assert 'class="lb-home-header"' in body
    assert 'class="lb-intro-stmt"' in body
    assert 'class="lb-equip"' in body
    assert 'class="lb-topo' in body
    assert 'class="lb-quick' in body
    assert 'class="lb-start' in body


def test_lang_query_param_sets_cookie_and_flips_strings(http: httpx.Client) -> None:
    r = http.get("/?lang=ru", follow_redirects=False)
    assert r.status_code == 200
    assert "Зарегистрированные лаборатории" in r.text
    assert r.cookies.get("lang") == "ru"


def test_api_public_labs_returns_list(http: httpx.Client) -> None:
    r = http.get("/api/public/labs")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)


def test_root_is_not_a_redirect(http: httpx.Client) -> None:
    r = http.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "Location" not in r.headers
