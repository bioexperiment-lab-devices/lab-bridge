"""WHEP egress endpoint — browser viewers subscribe here."""

from __future__ import annotations

import asyncio
from typing import Protocol

from aiortc import RTCSessionDescription
from fastapi import APIRouter, HTTPException, Path, Request, Response
from ulid import ULID

from app.auth import RequiredGroupsDep
from app.control import CameraBusy, ControlError
from app.discovery import TranslationDescriptor
from app.session_manager import Session, SessionManager
from app.sfu import new_peer_connection, rewrite_sdp_with_public_ip


class _DiscoveryLike(Protocol):
    async def list(
        self, lab_name: str, *, force_refresh: bool = False
    ) -> list[TranslationDescriptor]: ...


class _ControlLike(Protocol):
    async def start(self, **kwargs: object) -> object: ...
    async def stop(self, **kwargs: object) -> None: ...


def make_router(
    *,
    manager: SessionManager,
    discovery: _DiscoveryLike,
    control: _ControlLike,
    public_ip: str,
    publish_ready_timeout_s: float,
    drain_debounce_s: float,
    max_subscribers_per_session: int,
    base_url: str,
) -> APIRouter:
    router = APIRouter()

    # Reverse map for DELETE: sub_id (ULID, URL-safe) → owning Session.
    # Translation IDs may contain '/', '?', '\' (e.g. Windows DirectShow
    # device paths), so we never embed them in the DELETE URL — DELETE
    # uses sub_id alone.
    sub_to_session: dict[str, Session] = {}

    async def _stop_session(session: Session) -> None:
        try:
            await control.stop(
                lab_name=session.lab_name,
                translation_id=session.translation_id,
                session_id=session.session_id,
            )
        finally:
            if session.publisher_pc is not None:
                await session.publisher_pc.close()
            for sub_id, pc in list(session.subscribers.items()):
                await pc.close()
                sub_to_session.pop(sub_id, None)
            session.subscribers.clear()
            manager.drop(session)

    # translation_id uses the `:path` converter because SerialHop-assigned
    # IDs may contain '/' (Windows DirectShow device paths, etc.). After
    # uvicorn percent-decodes the URL, multi-segment IDs would otherwise
    # fail the default single-segment route matcher.
    @router.post("/streamer/whep/{lab}/{translation_id:path}")
    async def whep_post(
        request: Request,
        lab: str = Path(..., min_length=1, max_length=128),
        translation_id: str = Path(..., min_length=1, max_length=512),
        _identity=RequiredGroupsDep,
    ) -> Response:
        offer_sdp = (await request.body()).decode("utf-8")

        async with manager.lock_for(lab, translation_id):
            session = manager.get(lab, translation_id)
            if session is None:
                armed = await discovery.list(lab)
                if not any(t.id == translation_id for t in armed):
                    raise HTTPException(status_code=404, detail="translation not armed")
                session = manager.create(lab_name=lab, translation_id=translation_id)
                whip_url = f"{base_url}/streamer/whip/{session.session_id}"
                try:
                    await control.start(
                        lab_name=lab,
                        translation_id=translation_id,
                        session_id=session.session_id,
                        whip_url=whip_url,
                        whip_token=session.publish_token.value,
                    )
                except CameraBusy:
                    manager.drop(session)
                    raise HTTPException(status_code=503, detail="camera unavailable")
                except ControlError:
                    manager.drop(session)
                    raise HTTPException(status_code=502, detail="lab unreachable")

        manager.cancel_drain(session)

        try:
            await asyncio.wait_for(session.publish_ready.wait(), timeout=publish_ready_timeout_s)
        except asyncio.TimeoutError:
            # Best-effort cleanup; drop session so next viewer retries fresh.
            await _stop_session(session)
            raise HTTPException(status_code=504, detail="publisher did not attach")

        if session.subscriber_count() >= max_subscribers_per_session:
            raise HTTPException(status_code=429, detail="max subscribers reached")

        sub_pc = new_peer_connection()
        sub_pc.addTrack(session.publisher_track)

        @sub_pc.on("connectionstatechange")
        def _on_state() -> None:
            state = getattr(sub_pc, "connectionState", "")
            if state in ("failed", "closed"):
                _remove_subscriber_sync(session, sub_pc)

        await sub_pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp, type="offer"))
        await sub_pc.setLocalDescription(await sub_pc.createAnswer())

        sub_id = str(ULID())
        session.subscribers[sub_id] = sub_pc
        sub_to_session[sub_id] = session

        answer = rewrite_sdp_with_public_ip(sub_pc.localDescription.sdp, public_ip=public_ip)
        # DELETE URL is sub-id-only so it stays URL-safe regardless of what
        # the translation_id contains.
        return Response(
            content=answer,
            media_type="application/sdp",
            status_code=201,
            headers={"Location": f"/streamer/whep/sub/{sub_id}"},
        )

    @router.delete("/streamer/whep/sub/{sub_id}")
    async def whep_delete(
        sub_id: str = Path(..., min_length=1, max_length=64),
        _identity=RequiredGroupsDep,
    ) -> Response:
        session = sub_to_session.pop(sub_id, None)
        if session is not None:
            pc = session.subscribers.pop(sub_id, None)
            if pc is not None:
                await pc.close()
            if session.subscriber_count() == 0:
                manager.schedule_drain(
                    session,
                    debounce_s=drain_debounce_s,
                    on_expire=_stop_session,
                )
        return Response(status_code=204)

    def _remove_subscriber_sync(session: Session, pc: object) -> None:
        for sub_id, candidate in list(session.subscribers.items()):
            if candidate is pc:
                session.subscribers.pop(sub_id, None)
                sub_to_session.pop(sub_id, None)
                break
        if session.subscriber_count() == 0:
            manager.schedule_drain(
                session,
                debounce_s=drain_debounce_s,
                on_expire=_stop_session,
            )

    return router
