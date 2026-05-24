from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.discovery import DiscoveryCache, TranslationDescriptor
from app.session_manager import SessionManager
from app.whep import make_router


class _StubDiscovery:
    def __init__(self, armed: dict[str, list[TranslationDescriptor]]) -> None:
        self._armed = armed

    async def list(
        self, lab_name: str, *, force_refresh: bool = False
    ) -> list[TranslationDescriptor]:
        return list(self._armed.get(lab_name, []))


class _StubControl:
    def __init__(self, *, raise_on_start: Exception | None = None) -> None:
        self.starts: list[dict[str, str]] = []
        self.stops: list[dict[str, str]] = []
        self._raise_on_start = raise_on_start

    async def start(self, **kwargs: object) -> object:
        if self._raise_on_start is not None:
            raise self._raise_on_start
        self.starts.append({k: str(v) for k, v in kwargs.items()})
        return MagicMock(session_id=kwargs["session_id"])

    async def stop(self, **kwargs: object) -> None:
        self.stops.append({k: str(v) for k, v in kwargs.items()})


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager(whip_token_validity_s=60.0)


def _app(
    manager: SessionManager,
    discovery: object,
    control: object,
    *,
    public_ip: str = "1.2.3.4",
    publish_ready_timeout_s: float = 0.2,
    drain_debounce_s: float = 0.1,
    max_subscribers: int = 3,
) -> FastAPI:
    fast = FastAPI()
    fast.dependency_overrides = {}
    # Bypass Authelia for unit tests by faking the identity dependency.
    from app.auth import get_remote_identity, Identity

    def _fake_identity() -> Identity:
        return Identity(user="alice", groups=["researchers"])

    fast.dependency_overrides[get_remote_identity] = _fake_identity
    fast.include_router(
        make_router(
            manager=manager,
            discovery=discovery,
            control=control,
            public_ip=public_ip,
            publish_ready_timeout_s=publish_ready_timeout_s,
            drain_debounce_s=drain_debounce_s,
            max_subscribers_per_session=max_subscribers,
            base_url="https://lab.example.com",
        )
    )
    return fast


def _fake_pc() -> MagicMock:
    pc = MagicMock()
    pc.setRemoteDescription = AsyncMock()
    pc.createAnswer = AsyncMock(return_value=MagicMock(sdp="v=0\r\n", type="answer"))
    pc.setLocalDescription = AsyncMock()
    pc.localDescription = MagicMock(sdp="v=0\r\n")
    pc.addTrack = MagicMock()
    pc.close = AsyncMock()
    return pc


def test_whep_404_when_translation_not_armed(manager: SessionManager) -> None:
    app = _app(manager, _StubDiscovery({}), _StubControl())
    r = TestClient(app).post(
        "/streamer/whep/alice/cam-0",
        headers={"Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 404


def test_whep_502_when_control_unreachable(manager: SessionManager) -> None:
    from app.control import ControlError

    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl(raise_on_start=ControlError("no tunnel"))
    app = _app(manager, discovery, control)
    r = TestClient(app).post(
        "/streamer/whep/alice/cam-0",
        headers={"Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 502


def test_whep_503_when_camera_busy(manager: SessionManager) -> None:
    from app.control import CameraBusy

    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl(raise_on_start=CameraBusy("camera busy"))
    app = _app(manager, discovery, control)
    r = TestClient(app).post(
        "/streamer/whep/alice/cam-0",
        headers={"Content-Type": "application/sdp"},
        content="v=0\r\n",
    )
    assert r.status_code == 503


def test_whep_504_when_publisher_never_arrives(manager: SessionManager) -> None:
    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl()
    app = _app(manager, discovery, control, publish_ready_timeout_s=0.05)

    with patch("app.whep.new_peer_connection", return_value=_fake_pc()):
        r = TestClient(app).post(
            "/streamer/whep/alice/cam-0",
            headers={"Content-Type": "application/sdp"},
            content="v=0\r\n",
        )
    assert r.status_code == 504


def test_whep_first_viewer_triggers_start(manager: SessionManager) -> None:
    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl()
    app = _app(manager, discovery, control, publish_ready_timeout_s=0.05)

    with patch("app.whep.new_peer_connection", return_value=_fake_pc()):
        TestClient(app).post(
            "/streamer/whep/alice/cam-0",
            headers={"Content-Type": "application/sdp"},
            content="v=0\r\n",
        )
    assert len(control.starts) == 1
    assert control.starts[0]["lab_name"] == "alice"
    assert control.starts[0]["translation_id"] == "cam-0"


def test_whep_201_when_publisher_already_attached(manager: SessionManager) -> None:
    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl()
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=MagicMock())

    fake_pc = _fake_pc()
    app = _app(manager, discovery, control)
    with patch("app.whep.new_peer_connection", return_value=fake_pc):
        r = TestClient(app).post(
            "/streamer/whep/alice/cam-0",
            headers={"Content-Type": "application/sdp"},
            content="v=0\r\n",
        )
    assert r.status_code == 201
    assert r.headers["Location"].startswith("/streamer/whep/alice/cam-0/")
    fake_pc.addTrack.assert_called_once()


def test_whep_429_when_max_subscribers(manager: SessionManager) -> None:
    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl()
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=MagicMock())
    s.subscribers["a"] = MagicMock()

    app = _app(manager, discovery, control, max_subscribers=1)
    with patch("app.whep.new_peer_connection", return_value=_fake_pc()):
        r = TestClient(app).post(
            "/streamer/whep/alice/cam-0",
            headers={"Content-Type": "application/sdp"},
            content="v=0\r\n",
        )
    assert r.status_code == 429


def test_whep_delete_removes_subscriber(manager: SessionManager) -> None:
    discovery = _StubDiscovery({"alice": [TranslationDescriptor(id="cam-0", label="Side")]})
    control = _StubControl()
    s = manager.create(lab_name="alice", translation_id="cam-0")
    sub_pc = MagicMock()
    sub_pc.close = AsyncMock()
    s.subscribers["sub-A"] = sub_pc

    app = _app(manager, discovery, control)
    r = TestClient(app).request("DELETE", "/streamer/whep/alice/cam-0/sub-A")
    assert r.status_code == 204
    assert "sub-A" not in s.subscribers
    sub_pc.close.assert_awaited_once()
