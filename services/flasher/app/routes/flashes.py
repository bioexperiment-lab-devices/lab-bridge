from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.backups import get_backup, download_backup_bytes
from app.clients import load_roster
from app.config import Settings
from app.firmware import (
    FirmwareNotFound,
    download_firmware_bytes,
    get_firmware,
    update_firmware,
)
from app.flash import run_flash_job
from app.flashes import (
    FlashNotFound,
    FlashStillRunning,
    create_running_flash,
    get_flash,
    get_running_flash,
    list_flashes,
    set_note,
)
from app.serialhop import SerialHopClient


_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_background_tasks: set[asyncio.Task[None]] = set()


class _Source(BaseModel):
    kind: str
    id: str


class _TestOverride(BaseModel):
    command: str
    expected_response: str


class _FlashPost(BaseModel):
    client: str = Field(min_length=1, max_length=128)
    port: str = Field(min_length=1, max_length=128)
    source: _Source
    test_override: _TestOverride | None = None
    save_test_to_record: bool = False
    skip_backup: bool = False


class _NotePatch(BaseModel):
    note: str


class _ReplayPost(BaseModel):
    client: str | None = None
    port: str | None = None


def _validate_hex(value: str) -> None:
    if not value or len(value) % 2 != 0 or not _HEX_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid request",
                "detail": f"not a valid hex string: {value!r}",
            },
        )


def make_router(settings: Settings, conn_factory, blobs_root: Path) -> APIRouter:
    router = APIRouter()
    f_blobs = blobs_root / "firmware"
    b_blobs = blobs_root / "backups"

    async def _resolve_source(
        conn, source: _Source
    ) -> tuple[str, str, str | None, str | None, str]:
        """Returns (firmware_name, firmware_sha256, test_command, expected_response, hex_text)."""
        if source.kind == "firmware":
            row = await get_firmware(conn, firmware_id=source.id)
            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown source",
                        "detail": source.id,
                    },
                )
            hex_text = await download_firmware_bytes(f_blobs, firmware_id=source.id)
            return (
                row["name"],
                row["sha256"],
                row["test_command"],
                row["expected_response"],
                hex_text,
            )
        if source.kind == "backup":
            row = await get_backup(conn, backup_id=source.id)
            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown source",
                        "detail": source.id,
                    },
                )
            hex_text = await download_backup_bytes(b_blobs, backup_id=source.id)
            return (
                row["name"],
                row["sha256"],
                row["test_command"],
                row["expected_response"],
                hex_text,
            )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid request",
                "detail": f"unknown source.kind: {source.kind!r}",
            },
        )

    @router.post("/api/flash")
    async def post_flash(body: _FlashPost) -> dict[str, str]:
        if body.test_override is not None:
            _validate_hex(body.test_override.command)
            _validate_hex(body.test_override.expected_response)

        # Look up the lab machine roster entry.
        roster = load_roster(settings.clients_file)
        entry = roster.get(body.client)
        if entry is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "unknown client",
                    "detail": body.client,
                },
            )

        # Pull port snapshot from a fresh SerialHop call.
        sh = SerialHopClient(host=settings.chisel_host, port=entry["port"])
        try:
            ports_body = await sh.get_ports_detailed()
        except Exception:  # validation continues — port_snapshot may be empty
            ports_body = {"ports": []}
        snap = next(
            (p for p in ports_body.get("ports", []) if p.get("name") == body.port),
            None,
        )
        port_snapshot = {
            "vid": (snap or {}).get("vid", ""),
            "pid": (snap or {}).get("pid", ""),
            "serial_number": (snap or {}).get("serial_number", ""),
            "product": (snap or {}).get("product", ""),
        }

        async with conn_factory() as conn:
            (fw_name, fw_sha, src_tcmd, src_eresp, hex_text) = await _resolve_source(
                conn, body.source
            )

            if body.test_override is not None:
                tcmd = body.test_override.command.lower()
                eresp = body.test_override.expected_response.lower()
                if body.save_test_to_record and body.source.kind == "firmware":
                    try:
                        await update_firmware(
                            conn,
                            firmware_id=body.source.id,
                            test_command=tcmd,
                            expected_response=eresp,
                        )
                    except FirmwareNotFound:
                        # already handled by _resolve_source above, defensive
                        raise HTTPException(
                            status_code=404,
                            detail={
                                "error": "unknown source",
                                "detail": body.source.id,
                            },
                        )
                # NOTE: save-back for backup source is intentionally not supported here —
                # the spec wires the explicit save toggle on firmware records only.
            else:
                tcmd = src_tcmd
                eresp = src_eresp

            flash_id = await create_running_flash(
                conn,
                client=body.client,
                port_name=body.port,
                port_snapshot=port_snapshot,
                source_kind=body.source.kind,
                source_id=body.source.id,
                firmware_sha256=fw_sha,
                firmware_name=fw_name,
                test_command_used=tcmd,
                expected_response_used=eresp,
                skip_backup=body.skip_backup,
            )

        task = asyncio.create_task(
            run_flash_job(
                conn_factory=conn_factory,
                blobs_root=blobs_root,
                flash_id=flash_id,
                client=sh,
                port=body.port,
                firmware=hex_text,
                test_command=tcmd,
                expected_response=eresp,
                skip_backup=body.skip_backup,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"job_id": flash_id}

    @router.get("/api/flash/current")
    async def current() -> dict[str, Any]:
        async with conn_factory() as conn:
            row = await get_running_flash(conn)
        return row or {}

    @router.get("/api/flash/{flash_id}")
    async def get_one(flash_id: str) -> dict[str, Any]:
        async with conn_factory() as conn:
            row = await get_flash(conn, flash_id=flash_id)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown flash",
                    "detail": flash_id,
                },
            )
        return row

    @router.get("/api/flashes")
    async def list_(
        client: list[str] = Query(default_factory=list),
        outcome: list[str] = Query(default_factory=list),
        source_kind: str | None = None,
        source_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 50,
        before: str | None = None,
    ) -> dict[str, Any]:
        async with conn_factory() as conn:
            return await list_flashes(
                conn,
                client=client or None,
                outcome=outcome or None,
                source_kind=source_kind,
                source_id=source_id,
                since=since,
                until=until,
                limit=limit,
                before=before,
            )

    @router.patch("/api/flashes/{flash_id}/note")
    async def patch_note(flash_id: str, body: _NotePatch) -> dict[str, str]:
        async with conn_factory() as conn:
            try:
                await set_note(conn, flash_id=flash_id, note=body.note)
            except FlashNotFound:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown flash",
                        "detail": flash_id,
                    },
                )
            except FlashStillRunning:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "invalid request",
                        "detail": "cannot annotate while flash is running",
                    },
                )
        return {"note": body.note}

    @router.post("/api/flashes/{flash_id}/replay")
    async def replay(flash_id: str, body: _ReplayPost) -> dict[str, str]:
        async with conn_factory() as conn:
            original = await get_flash(conn, flash_id=flash_id)
        if original is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown flash",
                    "detail": flash_id,
                },
            )
        # Verify source still exists.
        async with conn_factory() as conn:
            if original["source_kind"] == "firmware":
                src = await get_firmware(conn, firmware_id=original["source_id"])
            elif original["source_kind"] == "backup":
                src = await get_backup(conn, backup_id=original["source_id"])
            else:
                src = None
        if src is None:
            raise HTTPException(
                status_code=410,
                detail={
                    "error": "source deleted",
                    "detail": f"{original['source_kind']} {original['source_id']} no longer exists",
                },
            )
        # Reconstruct a POST body and call it.
        return await post_flash(
            _FlashPost(
                client=body.client or original["client"],
                port=body.port or original["port_name"],
                source=_Source(kind=original["source_kind"], id=original["source_id"]),
                test_override=(
                    _TestOverride(
                        command=original["test_command_used"],
                        expected_response=original["expected_response_used"],
                    )
                    if original["test_command_used"]
                    else None
                ),
                save_test_to_record=False,
                skip_backup=bool(original["skip_backup"]),
            )
        )

    return router
