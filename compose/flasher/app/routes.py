from __future__ import annotations

import asyncio
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
    async def get_clients() -> dict[str, Any]:
        roster = load_roster(settings.clients_file)
        names_ports = [(name, roster[name]["port"]) for name in sorted(roster)]
        if not names_ports:
            return {"clients": []}
        results = await asyncio.gather(
            *(asyncio.to_thread(probe_tcp, settings.chisel_host, port) for _, port in names_ports)
        )
        out = [
            {"name": name, "port": port}
            for (name, port), online in zip(names_ports, results, strict=True)
            if online
        ]
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
