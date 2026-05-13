from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel, Field

from app.clients import load_roster, probe_tcp
from app.config import Settings
from app.flash import JobStore, run_flash_job
from app.serialhop import SerialHopClient, UpstreamErrorResponse, UpstreamUnreachable

MAX_FIRMWARE_BYTES = 256 * 1024
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


class _TestPair(BaseModel):
    command: str
    expected_response: str


class _FlashRequest(BaseModel):
    client: str = Field(min_length=1, max_length=128)
    port: str = Field(min_length=1, max_length=128)
    firmware: str
    test: _TestPair | None = None


def _validate_hex(value: str) -> None:
    if not value or len(value) % 2 != 0 or not _HEX_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid request", "detail": f"not a valid hex string: {value!r}"},
        )


def make_router(settings: Settings, store: JobStore) -> APIRouter:
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

    @router.post("/api/flash")
    async def post_flash(req: _FlashRequest) -> dict[str, str]:
        if not req.firmware:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid request", "detail": "firmware is empty"},
            )
        if len(req.firmware.encode("utf-8")) > MAX_FIRMWARE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid request", "detail": "firmware exceeds 256 KiB"},
            )
        roster = load_roster(settings.clients_file)
        entry = roster.get(req.client)
        if entry is None:
            raise HTTPException(
                status_code=400,
                detail={"error": "unknown client", "detail": req.client},
            )
        if req.test is not None:
            _validate_hex(req.test.command)
            _validate_hex(req.test.expected_response)
            test_command = req.test.command.lower()
            expected_response = req.test.expected_response.lower()
        else:
            test_command = None
            expected_response = None

        sha = hashlib.sha256(req.firmware.encode("utf-8")).hexdigest()
        job_id = store.create(
            client=req.client,
            port=req.port,
            firmware_sha256=sha,
            firmware_size=len(req.firmware),
        )
        client_obj = _build_client(entry["port"])
        asyncio.create_task(
            run_flash_job(
                store=store,
                job_id=job_id,
                client=client_obj,
                port=req.port,
                firmware=req.firmware,
                test_command=test_command,
                expected_response=expected_response,
            )
        )
        return {"job_id": job_id}

    # Declared before the parameterized path so the literal segment wins.
    @router.get("/api/flash/current")
    def get_flash_current() -> dict[str, Any]:
        current = store.current()
        return current if current is not None else {}

    @router.get("/api/flash/{job_id}")
    def get_flash(job_id: str = PathParam(..., min_length=1, max_length=64)) -> dict[str, Any]:
        record = store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="unknown job")
        return record

    return router
