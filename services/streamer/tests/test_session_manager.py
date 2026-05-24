from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.session_manager import Session, SessionManager, SessionState


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager(whip_token_validity_s=60.0)


def test_create_session_yields_unique_session_id(manager: SessionManager) -> None:
    a = manager.create(lab_name="alice", translation_id="cam-0")
    b = manager.create(lab_name="alice", translation_id="cam-1")
    assert a.session_id != b.session_id


def test_create_session_initial_state_is_created(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    assert s.state == SessionState.CREATED
    assert s.publish_token is not None
    assert s.publisher_track is None


def test_get_returns_existing(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    assert manager.get("alice", "cam-0") is s


def test_get_returns_none_when_missing(manager: SessionManager) -> None:
    assert manager.get("alice", "cam-0") is None


def test_get_by_session_id(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    assert manager.get_by_session_id(s.session_id) is s


def test_get_by_session_id_returns_none_when_missing(manager: SessionManager) -> None:
    assert manager.get_by_session_id("01NOPE") is None


def test_drop_removes_session(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    manager.drop(s)
    assert manager.get("alice", "cam-0") is None
    assert manager.get_by_session_id(s.session_id) is None


def test_mark_publishing_transitions_state(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=object())
    assert s.state == SessionState.PUBLISHING
    assert s.publisher_track is not None


def test_publish_ready_event_set_on_mark_publishing(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    assert not s.publish_ready.is_set()
    s.mark_publishing(track=object())
    assert s.publish_ready.is_set()


def test_subscriber_register_and_remove(manager: SessionManager) -> None:
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=object())
    sub_id = s.add_subscriber(object())
    assert s.subscriber_count() == 1
    s.remove_subscriber(sub_id)
    assert s.subscriber_count() == 0


async def test_lock_serializes_concurrent_creates(manager: SessionManager) -> None:
    """Two concurrent first-viewer arrivals must result in one session."""
    started: list[str] = []

    async def viewer() -> None:
        async with manager.lock_for("alice", "cam-0"):
            existing = manager.get("alice", "cam-0")
            if existing is None:
                s = manager.create(lab_name="alice", translation_id="cam-0")
                started.append(s.session_id)
            await asyncio.sleep(0.01)

    await asyncio.gather(viewer(), viewer(), viewer())
    assert len(started) == 1
    assert manager.get("alice", "cam-0") is not None


async def test_drain_scheduling_emits_stop_after_debounce() -> None:
    fired: list[Session] = []

    async def _on_drain(session: Session) -> None:
        fired.append(session)

    manager = SessionManager(whip_token_validity_s=60.0)
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=object())
    sub_id = s.add_subscriber(object())
    s.remove_subscriber(sub_id)

    manager.schedule_drain(s, debounce_s=0.05, on_expire=_on_drain)
    await asyncio.sleep(0.02)
    assert fired == []
    await asyncio.sleep(0.06)
    assert fired == [s]


async def test_drain_cancelled_by_new_subscriber() -> None:
    fired: list[Session] = []

    async def _on_drain(session: Session) -> None:
        fired.append(session)

    manager = SessionManager(whip_token_validity_s=60.0)
    s = manager.create(lab_name="alice", translation_id="cam-0")
    s.mark_publishing(track=object())
    sub_id = s.add_subscriber(object())
    s.remove_subscriber(sub_id)

    manager.schedule_drain(s, debounce_s=0.1, on_expire=_on_drain)
    await asyncio.sleep(0.02)
    manager.cancel_drain(s)
    s.add_subscriber(object())
    await asyncio.sleep(0.15)
    assert fired == []
