from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from app.config import Settings
from app.firmware import (
    FirmwareInUse,
    FirmwareNotFound,
    create_firmware,
    delete_firmware,
    download_firmware_bytes,
    get_firmware,
    get_firmware_by_sha256,
    list_firmware,
    update_firmware,
)
from app.tags import TagNotFound

MAX_FIRMWARE_BYTES = 256 * 1024


class _FirmwarePost(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    firmware: str
    test_command: str | None = None
    expected_response: str | None = None
    original_filename: str | None = None
    tags: list[str] = Field(default_factory=list)


class _FirmwarePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    test_command: str | None = None
    expected_response: str | None = None
    tags: list[str] | None = None
    # Sentinels: PATCH treats `test_command` / `expected_response` of `None`
    # in the JSON body as "set to NULL". An absent key means "do not touch".
    # FastAPI's model_dump(exclude_unset=True) handles that.


def _validate_firmware_bytes(body: _FirmwarePost) -> None:
    if not body.firmware:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid request",
                "detail": "firmware is empty",
            },
        )
    if len(body.firmware.encode("utf-8")) > MAX_FIRMWARE_BYTES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid request",
                "detail": "firmware exceeds 256 KiB",
            },
        )


def _require_bearer(authorization: str | None, expected: str) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "bearer required",
                "detail": "Authorization: Bearer <token> required",
            },
        )
    provided = authorization[len("Bearer ") :]
    # compare_digest avoids a timing side-channel and accepts unequal-length
    # inputs without raising. Mirrors services/flasher/app/routes/agent.py.
    if not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "bearer invalid",
                "detail": "token does not match",
            },
        )


def make_router(settings: Settings, conn_factory, blobs_root: Path) -> APIRouter:
    router = APIRouter()
    fw_blobs = blobs_root / "firmware"

    # ----- Operator endpoints -----

    @router.get("/api/firmware")
    async def operator_list(
        tag: list[str] = Query(default_factory=list),
        q: str | None = None,
        limit: int = 100,
        before: str | None = None,
    ) -> dict[str, Any]:
        async with conn_factory() as conn:
            return await list_firmware(conn, tag_ids=tag, q=q, limit=limit, before=before)

    @router.get("/api/firmware/{firmware_id}")
    async def operator_get(firmware_id: str) -> dict[str, Any]:
        async with conn_factory() as conn:
            row = await get_firmware(conn, firmware_id=firmware_id)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown firmware",
                    "detail": firmware_id,
                },
            )
        return row

    @router.post("/api/firmware")
    async def operator_post(body: _FirmwarePost) -> dict[str, Any]:
        _validate_firmware_bytes(body)
        async with conn_factory() as conn:
            try:
                return await create_firmware(
                    conn,
                    blobs_dir=fw_blobs,
                    name=body.name,
                    description=body.description,
                    firmware=body.firmware,
                    test_command=body.test_command,
                    expected_response=body.expected_response,
                    original_filename=body.original_filename,
                    tag_ids=body.tags,
                )
            except TagNotFound as exc:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "tag not found",
                        "detail": str(exc),
                    },
                )

    @router.patch("/api/firmware/{firmware_id}")
    async def operator_patch(firmware_id: str, body: _FirmwarePatch) -> dict[str, Any]:
        kwargs = body.model_dump(exclude_unset=True)
        if "tags" in kwargs:
            kwargs["tag_ids"] = kwargs.pop("tags")
        async with conn_factory() as conn:
            try:
                return await update_firmware(conn, firmware_id=firmware_id, **kwargs)
            except FirmwareNotFound:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown firmware",
                        "detail": firmware_id,
                    },
                )
            except TagNotFound as exc:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "tag not found",
                        "detail": str(exc),
                    },
                )

    @router.delete("/api/firmware/{firmware_id}")
    async def operator_delete(firmware_id: str) -> dict[str, str]:
        async with conn_factory() as conn:
            try:
                await delete_firmware(conn, blobs_dir=fw_blobs, firmware_id=firmware_id)
            except FirmwareInUse:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "cannot delete: flash in flight",
                        "detail": firmware_id,
                    },
                )
            except FirmwareNotFound:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown firmware",
                        "detail": firmware_id,
                    },
                )
        return {"status": "deleted"}

    @router.get("/api/firmware/{firmware_id}/download")
    async def operator_download(firmware_id: str) -> Response:
        async with conn_factory() as conn:
            row = await get_firmware(conn, firmware_id=firmware_id)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown firmware",
                    "detail": firmware_id,
                },
            )
        body = await download_firmware_bytes(fw_blobs, firmware_id=firmware_id)
        filename = row["original_filename"] or f"{firmware_id}.hex"
        return PlainTextResponse(
            content=body,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ----- Bearer-auth endpoints -----

    @router.post("/api/v1/firmware")
    async def bearer_post(
        body: _FirmwarePost,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_bearer(authorization, settings.upload_token)
        _validate_firmware_bytes(body)
        async with conn_factory() as conn:
            try:
                return await create_firmware(
                    conn,
                    blobs_dir=fw_blobs,
                    name=body.name,
                    description=body.description,
                    firmware=body.firmware,
                    test_command=body.test_command,
                    expected_response=body.expected_response,
                    original_filename=body.original_filename,
                    tag_ids=body.tags,
                )
            except TagNotFound as exc:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "tag not found",
                        "detail": str(exc),
                    },
                )

    @router.get("/api/v1/firmware")
    async def bearer_get_by_sha256(
        sha256: str = Query(),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_bearer(authorization, settings.upload_token)
        async with conn_factory() as conn:
            row = await get_firmware_by_sha256(conn, sha256=sha256)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown firmware",
                    "detail": sha256,
                },
            )
        return row

    @router.get("/api/firmware/{firmware_id}/flashes")
    async def operator_flashes(
        firmware_id: str, limit: int = 50, before: str | None = None
    ) -> dict[str, Any]:
        from app.flashes import list_flashes

        async with conn_factory() as conn:
            return await list_flashes(
                conn,
                source_kind="firmware",
                source_id=firmware_id,
                limit=limit,
                before=before,
            )

    return router
