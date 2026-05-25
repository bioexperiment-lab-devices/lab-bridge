from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.session_manager import SessionManager
from app.whip import make_router


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager(whip_token_validity_s=60.0)


@pytest.fixture
def app(manager: SessionManager) -> FastAPI:
    fast = FastAPI()
    fast.include_router(make_router(manager=manager, public_ip="1.2.3.4"))
    return fast


def test_whip_404_when_session_unknown(app: FastAPI) -> None:
    client = TestClient(app)
    r = client.post(
        "/streamer/whip/01NOPE",
        headers={"Authorization": "Bearer tk_anything", "Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 404


def test_whip_401_when_bearer_missing(app: FastAPI, manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    client = TestClient(app)
    r = client.post(
        f"/streamer/whip/{s.session_id}",
        headers={"Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 401


def test_whip_401_when_bearer_wrong(app: FastAPI, manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    client = TestClient(app)
    r = client.post(
        f"/streamer/whip/{s.session_id}",
        headers={"Authorization": "Bearer tk_wrong", "Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 401


def test_whip_410_when_token_already_burned(app: FastAPI, manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.publish_token.burn()
    client = TestClient(app)
    r = client.post(
        f"/streamer/whip/{s.session_id}",
        headers={
            "Authorization": f"Bearer {s.publish_token.value}",
            "Content-Type": "application/sdp",
        },
        content="v=0\r\n",
    )
    assert r.status_code == 410


def test_whip_201_negotiates_and_burns_token(app: FastAPI, manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    bearer = s.publish_token.value

    fake_pc = MagicMock()
    fake_pc.setRemoteDescription = AsyncMock()
    fake_pc.createAnswer = AsyncMock(return_value=MagicMock(sdp="v=0\r\n", type="answer"))
    fake_pc.setLocalDescription = AsyncMock()
    fake_pc.localDescription = MagicMock(
        sdp="v=0\r\na=candidate:1 1 udp 1 10.0.0.1 50001 typ host\r\n"
    )

    with patch("app.whip.new_peer_connection", return_value=fake_pc):
        client = TestClient(app)
        r = client.post(
            f"/streamer/whip/{s.session_id}",
            headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/sdp"},
            content="v=0\r\n",
        )

    assert r.status_code == 201
    assert r.headers["Content-Type"].startswith("application/sdp")
    assert r.headers["Location"] == f"/streamer/whip/{s.session_id}"
    assert "1.2.3.4" in r.text  # candidate rewritten
    assert s.publish_token.matches(bearer) is False  # burned
    fake_pc.setRemoteDescription.assert_awaited_once()
    fake_pc.setLocalDescription.assert_awaited_once()


def test_whip_delete_204(app: FastAPI, manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.publisher_pc = MagicMock()
    s.publisher_pc.close = AsyncMock()
    s.publish_token.burn()  # bearer no longer matches; DELETE uses session_id only
    client = TestClient(app)
    r = client.request(
        "DELETE",
        f"/streamer/whip/{s.session_id}",
        headers={"Authorization": "Bearer ignored"},
    )
    assert r.status_code == 204
    s.publisher_pc.close.assert_awaited_once()


def test_whip_delete_404_when_unknown(app: FastAPI) -> None:
    client = TestClient(app)
    r = client.request("DELETE", "/streamer/whip/01NOPE")
    assert r.status_code == 404
