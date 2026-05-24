from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import Identity, get_remote_identity
from app.discovery import TranslationDescriptor
from app.pages import make_router


class _StubDiscovery:
    def __init__(self, armed: dict[str, list[TranslationDescriptor]]) -> None:
        self._armed = armed

    async def list(
        self, lab_name: str, *, force_refresh: bool = False
    ) -> list[TranslationDescriptor]:
        return list(self._armed.get(lab_name, []))


def _app(armed: dict[str, list[TranslationDescriptor]], roster: dict[str, int]) -> FastAPI:
    fast = FastAPI()
    fast.dependency_overrides[get_remote_identity] = lambda: Identity(
        user="alice", groups=["researchers"]
    )
    fast.include_router(
        make_router(roster=roster, discovery=_StubDiscovery(armed))
    )
    return fast


def test_picker_lists_all_roster_labs() -> None:
    app = _app(armed={}, roster={"alice": 8089, "bob": 8090})
    r = TestClient(app).get("/streamer/labs")
    assert r.status_code == 200
    body = r.text
    assert "alice" in body
    assert "bob" in body


def test_picker_active_when_translations_exist() -> None:
    armed = {"alice": [TranslationDescriptor(id="cam-0", label="Side")]}
    app = _app(armed=armed, roster={"alice": 8089, "bob": 8090})
    r = TestClient(app).get("/streamer/labs")
    body = r.text
    assert "data-lab=\"alice\"" in body
    assert "data-active=\"true\"" in body
    assert "data-active=\"false\"" in body  # bob


def test_api_labs_returns_active_state() -> None:
    armed = {"alice": [TranslationDescriptor(id="cam-0", label="Side")]}
    app = _app(armed=armed, roster={"alice": 8089, "bob": 8090})
    r = TestClient(app).get("/streamer/api/labs")
    assert r.status_code == 200
    payload = {row["name"]: row for row in r.json()}
    assert payload["alice"]["active"] is True
    assert payload["alice"]["translation_count"] == 1
    assert payload["bob"]["active"] is False
    assert payload["bob"]["translation_count"] == 0


def test_api_lab_translations() -> None:
    armed = {
        "alice": [
            TranslationDescriptor(id="cam-0", label="Side"),
            TranslationDescriptor(id="cam-1", label="Top"),
        ]
    }
    app = _app(armed=armed, roster={"alice": 8089})
    r = TestClient(app).get("/streamer/api/labs/alice/translations")
    assert r.status_code == 200
    assert r.json() == [
        {"id": "cam-0", "label": "Side"},
        {"id": "cam-1", "label": "Top"},
    ]


def test_api_lab_translations_unknown_lab_404() -> None:
    app = _app(armed={}, roster={"alice": 8089})
    r = TestClient(app).get("/streamer/api/labs/ghost/translations")
    assert r.status_code == 404


def test_lab_viewing_page_contains_translation_grid_stub() -> None:
    armed = {"alice": [TranslationDescriptor(id="cam-0", label="Side")]}
    app = _app(armed=armed, roster={"alice": 8089})
    r = TestClient(app).get("/streamer/labs/alice")
    assert r.status_code == 200
    assert "data-lab=\"alice\"" in r.text
    assert "streamer.js" in r.text


def test_lab_viewing_page_unknown_lab_404() -> None:
    app = _app(armed={}, roster={"alice": 8089})
    r = TestClient(app).get("/streamer/labs/ghost")
    assert r.status_code == 404
