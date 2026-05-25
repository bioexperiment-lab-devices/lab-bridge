"""WHIP ingest endpoint (RFC 9725) — SerialHop publishes media here."""

from __future__ import annotations

from typing import Any

from aiortc import RTCSessionDescription
from fastapi import APIRouter, Header, HTTPException, Path, Request, Response

from app.session_manager import Session, SessionManager
from app.sfu import new_peer_connection, rewrite_sdp_with_public_ip


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization.split(None, 1)[1].strip()


def make_router(*, manager: SessionManager, public_ip: str) -> APIRouter:
    router = APIRouter()

    @router.post("/streamer/whip/{session_id}")
    async def whip_post(
        request: Request,
        session_id: str = Path(..., min_length=1, max_length=64),
        authorization: str | None = Header(default=None),
    ) -> Response:
        session = manager.get_by_session_id(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="unknown session")

        bearer = _parse_bearer(authorization)
        if not session.publish_token.matches(bearer):
            if session.publish_token.is_burned:
                raise HTTPException(status_code=410, detail="token already redeemed")
            raise HTTPException(status_code=401, detail="invalid bearer")

        session.publish_token.burn()

        offer_sdp = (await request.body()).decode("utf-8")

        pc = new_peer_connection()
        session.publisher_pc = pc

        @pc.on("track")
        def _on_track(track: Any) -> None:
            session.mark_publishing(track=track)

        await pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp, type="offer"))
        await pc.setLocalDescription(await pc.createAnswer())

        answer = rewrite_sdp_with_public_ip(pc.localDescription.sdp, public_ip=public_ip)

        return Response(
            content=answer,
            media_type="application/sdp",
            status_code=201,
            headers={"Location": f"/streamer/whip/{session_id}"},
        )

    @router.delete("/streamer/whip/{session_id}")
    async def whip_delete(
        session_id: str = Path(..., min_length=1, max_length=64),
    ) -> Response:
        session = manager.get_by_session_id(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="unknown session")
        if session.publisher_pc is not None:
            await session.publisher_pc.close()
        return Response(status_code=204)

    return router


def session_for_delete(manager: SessionManager, session_id: str) -> Session | None:
    """Public helper for tests / e2e shutdown hooks."""
    return manager.get_by_session_id(session_id)
