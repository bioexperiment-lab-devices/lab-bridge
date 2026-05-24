"""Issue start/stop commands to SerialHop over the chisel reverse tunnel."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


class ControlError(Exception):
    """Generic control-plane failure (network, unknown lab, malformed reply)."""


class UnknownTranslation(ControlError):
    """SerialHop returned 404 — translation id not recognised."""


class CameraBusy(ControlError):
    """SerialHop returned 503 — camera hardware not available."""


@dataclass(frozen=True)
class StartResult:
    """Outcome of a successful start (202) or already-running (409)."""

    session_id: str


class ControlPlaneClient:
    def __init__(
        self,
        *,
        roster: dict[str, int],
        chisel_host: str,
        request_timeout_s: float,
    ) -> None:
        self._roster = roster
        self._host = chisel_host
        self._timeout_s = request_timeout_s

    async def start(
        self,
        *,
        lab_name: str,
        translation_id: str,
        session_id: str,
        whip_url: str,
        whip_token: str,
        ice_servers: list[dict[str, object]] | None = None,
    ) -> StartResult:
        url = self._url(lab_name, translation_id, "start")
        body = {
            "session_id": session_id,
            "whip_url": whip_url,
            "whip_token": whip_token,
            "ice_servers": list(ice_servers or []),
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.post(url, json=body)
        except (httpx.HTTPError, OSError) as exc:
            raise ControlError(f"start failed: {exc.__class__.__name__}") from exc

        if resp.status_code == 202:
            return StartResult(session_id=session_id)
        if resp.status_code == 404:
            raise UnknownTranslation(translation_id)
        if resp.status_code == 503:
            raise CameraBusy(translation_id)
        raise ControlError(f"unexpected start status: {resp.status_code}")

    async def stop(self, *, lab_name: str, translation_id: str, session_id: str) -> None:
        url = self._url(lab_name, translation_id, "stop")
        body = {"session_id": session_id}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                await client.post(url, json=body)
        except (httpx.HTTPError, OSError):
            # Best-effort: a lab that's gone can't be told anything anyway.
            return

    def _url(self, lab_name: str, translation_id: str, action: str) -> str:
        port = self._roster.get(lab_name)
        if port is None:
            raise ControlError(f"unknown lab: {lab_name}")
        return f"http://{self._host}:{port}/api/translations/{translation_id}/{action}"
