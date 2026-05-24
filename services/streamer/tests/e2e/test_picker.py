from __future__ import annotations

import httpx


def test_healthz_ok(http_streamer: httpx.Client) -> None:
    r = http_streamer.get("/healthz")
    assert r.status_code == 200


def test_picker_lists_alice(http_streamer: httpx.Client) -> None:
    r = http_streamer.get("/streamer/labs")
    assert r.status_code == 200
    assert "alice" in r.text


def test_api_labs_shows_active_with_armed_translation(
    http_streamer: httpx.Client, http_stub: httpx.Client
) -> None:
    r = http_streamer.get("/streamer/api/labs")
    assert r.status_code == 200
    rows = {row["name"]: row for row in r.json()}
    assert rows["alice"]["active"] is True
    assert rows["alice"]["translation_count"] == 1


def test_api_translations(http_streamer: httpx.Client) -> None:
    r = http_streamer.get("/streamer/api/labs/alice/translations")
    assert r.status_code == 200
    assert r.json() == [{"id": "cam-0", "label": "Test pattern"}]


def test_api_translations_unknown_lab_404(http_streamer: httpx.Client) -> None:
    r = http_streamer.get("/streamer/api/labs/ghost/translations")
    assert r.status_code == 404


def test_picker_blocks_unauthenticated() -> None:
    r = httpx.get("http://127.0.0.1:8080/streamer/labs", timeout=5.0)
    assert r.status_code == 401
