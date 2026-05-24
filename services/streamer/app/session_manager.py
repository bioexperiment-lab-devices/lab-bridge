"""In-memory Session state with locks, transitions, and debounced shutdown."""

from __future__ import annotations

import asyncio
import enum
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ulid import ULID

from app.tokens import WhipToken, generate_whip_token


class SessionState(enum.Enum):
    CREATED = "created"
    PUBLISHING = "publishing"
    DRAINING = "draining"


@dataclass
class Session:
    lab_name: str
    translation_id: str
    session_id: str
    publish_token: WhipToken
    state: SessionState = SessionState.CREATED
    publisher_pc: Any | None = None
    publisher_track: Any | None = None
    publish_ready: asyncio.Event = field(default_factory=asyncio.Event)
    subscribers: dict[str, Any] = field(default_factory=dict)

    def mark_publishing(self, *, track: Any) -> None:
        self.publisher_track = track
        self.state = SessionState.PUBLISHING
        self.publish_ready.set()

    def add_subscriber(self, pc: Any) -> str:
        sub_id = str(ULID())
        self.subscribers[sub_id] = pc
        return sub_id

    def remove_subscriber(self, sub_id: str) -> None:
        self.subscribers.pop(sub_id, None)

    def subscriber_count(self) -> int:
        return len(self.subscribers)


class SessionManager:
    """Owns the (lab, translation_id) → Session map and per-key locks."""

    def __init__(self, *, whip_token_validity_s: float) -> None:
        self._whip_token_validity_s = whip_token_validity_s
        self._sessions_by_key: dict[tuple[str, str], Session] = {}
        self._sessions_by_id: dict[str, Session] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._drain_tasks: dict[str, asyncio.Task[None]] = {}

    def lock_for(self, lab_name: str, translation_id: str) -> asyncio.Lock:
        key = (lab_name, translation_id)
        return self._locks.setdefault(key, asyncio.Lock())

    def get(self, lab_name: str, translation_id: str) -> Session | None:
        return self._sessions_by_key.get((lab_name, translation_id))

    def get_by_session_id(self, session_id: str) -> Session | None:
        return self._sessions_by_id.get(session_id)

    def create(self, *, lab_name: str, translation_id: str) -> Session:
        session = Session(
            lab_name=lab_name,
            translation_id=translation_id,
            session_id=str(ULID()),
            publish_token=generate_whip_token(validity_s=self._whip_token_validity_s),
        )
        self._sessions_by_key[(lab_name, translation_id)] = session
        self._sessions_by_id[session.session_id] = session
        return session

    def drop(self, session: Session) -> None:
        self._sessions_by_key.pop((session.lab_name, session.translation_id), None)
        self._sessions_by_id.pop(session.session_id, None)
        task = self._drain_tasks.pop(session.session_id, None)
        if task is not None and not task.done():
            task.cancel()

    def schedule_drain(
        self,
        session: Session,
        *,
        debounce_s: float,
        on_expire: Callable[[Session], Awaitable[None]],
    ) -> None:
        self.cancel_drain(session)
        session.state = SessionState.DRAINING

        async def _runner() -> None:
            try:
                await asyncio.sleep(debounce_s)
            except asyncio.CancelledError:
                return
            await on_expire(session)

        self._drain_tasks[session.session_id] = asyncio.create_task(_runner())

    def cancel_drain(self, session: Session) -> None:
        task = self._drain_tasks.pop(session.session_id, None)
        if task is not None and not task.done():
            task.cancel()
