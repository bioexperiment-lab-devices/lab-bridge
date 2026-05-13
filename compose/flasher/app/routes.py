from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Path as PathParam

from app.clients import load_roster, probe_tcp
from app.config import Settings
from app.serialhop import SerialHopClient, UpstreamErrorResponse, UpstreamUnreachable


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    def _build_client(port: int) -> SerialHopClient:
        return SerialHopClient(host=settings.chisel_host, port=port)

    @router.get("/api/clients")
    def get_clients() -> dict[str, Any]:
        roster = load_roster(settings.clients_file)
        out = []
        for name in sorted(roster):
            port = roster[name]["port"]
            if probe_tcp(settings.chisel_host, port):
                out.append({"name": name, "port": port})
        return {"clients": out}

    @router.get("/api/clients/{name}/ports")
    async def get_ports(
        name: str = PathParam(..., min_length=1, max_length=128),
    ) -> dict[str, Any]:
        roster = load_roster(settings.clients_file)
        entry = roster.get(name)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown client")
        client = _build_client(entry["port"])
        try:
            return await client.get_ports_detailed()
        except UpstreamErrorResponse as exc:
            raise HTTPException(
                status_code=502,
                detail={"error": exc.error_code, "detail": exc.detail},
            )
        except UpstreamUnreachable as exc:
            raise HTTPException(
                status_code=502,
                detail={"error": "upstream unreachable", "detail": exc.detail},
            )

    return router
