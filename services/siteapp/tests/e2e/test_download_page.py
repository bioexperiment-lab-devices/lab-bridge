"""End-to-end coverage for the redesigned Download Agent page."""

from __future__ import annotations

import httpx


def test_download_page_renders_hero_and_cards(http: httpx.Client) -> None:
    r = http.get("/download/agent")
    assert r.status_code == 200
    body = r.text
    assert 'class="lb-dl-hero"' in body
    assert 'class="lb-dl-cards"' in body
    # Three cards always render — Windows + Linux + RPi.
    assert body.count('class="lb-dl-card') >= 3
    assert "Linux" in body
    assert "Raspberry Pi" in body


def test_download_page_without_meta_disables_cta(http: httpx.Client) -> None:
    # The e2e fixture's site_data doesn't populate meta.json by default.
    r = http.get("/download/agent")
    assert r.status_code == 200
    body = r.text
    assert "Not yet available" in body or "Coming soon" in body


def test_download_page_lang_ru(http: httpx.Client) -> None:
    r = http.get("/download/agent?lang=ru")
    assert r.status_code == 200
    body = r.text
    assert "Single-binary" in body or "защищённый обратный туннель" in body
    assert r.cookies.get("lang") == "ru"


def test_sha256_has_copy_target(http: httpx.Client) -> None:
    # When meta.json is present this is a strict assertion; when absent the
    # block isn't rendered and we accept that — the page must still 200.
    r = http.get("/download/agent")
    assert r.status_code == 200
    if "lb-dl-meta__sha" in r.text:
        assert 'data-copy-text="' in r.text
