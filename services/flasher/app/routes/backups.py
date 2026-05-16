from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from app.backups import (
    BackupInUse,
    BackupNotFound,
    bulk_delete_backups,
    delete_backup,
    download_backup_bytes,
    get_backup,
    list_backups,
    update_backup,
)
from app.config import Settings
from app.firmware import create_firmware
from app.tags import TagNotFound


class _BackupPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    test_command: str | None = None
    expected_response: str | None = None


class _BulkDelete(BaseModel):
    ids: list[str]


class _Promote(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    copy_test_pair: bool = True


def make_router(settings: Settings, conn_factory, blobs_root: Path) -> APIRouter:
    router = APIRouter()
    b_blobs = blobs_root / "backups"
    f_blobs = blobs_root / "firmware"

    @router.get("/api/backups")
    async def list_(
        client: str | None = None,
        q: str | None = None,
        limit: int = 100,
        before: str | None = None,
    ) -> dict[str, Any]:
        async with conn_factory() as conn:
            return await list_backups(conn, client=client, q=q, limit=limit, before=before)

    @router.get("/api/backups/{backup_id}")
    async def get_one(backup_id: str) -> dict[str, Any]:
        async with conn_factory() as conn:
            row = await get_backup(conn, backup_id=backup_id)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown backup",
                    "detail": backup_id,
                },
            )
        return row

    @router.patch("/api/backups/{backup_id}")
    async def patch(backup_id: str, body: _BackupPatch) -> dict[str, Any]:
        kwargs = body.model_dump(exclude_unset=True)
        async with conn_factory() as conn:
            try:
                return await update_backup(conn, backup_id=backup_id, **kwargs)
            except BackupNotFound:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown backup",
                        "detail": backup_id,
                    },
                )

    @router.delete("/api/backups/{backup_id}")
    async def delete_one(backup_id: str) -> dict[str, str]:
        async with conn_factory() as conn:
            try:
                await delete_backup(conn, blobs_dir=b_blobs, backup_id=backup_id)
            except BackupNotFound:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown backup",
                        "detail": backup_id,
                    },
                )
            except BackupInUse:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "cannot delete: flash in flight",
                        "detail": backup_id,
                    },
                )
        return {"status": "deleted"}

    @router.post("/api/backups/bulk-delete")
    async def bulk_delete(body: _BulkDelete) -> dict[str, Any]:
        async with conn_factory() as conn:
            return await bulk_delete_backups(conn, blobs_dir=b_blobs, ids=body.ids)

    @router.get("/api/backups/{backup_id}/download")
    async def download(backup_id: str) -> Response:
        async with conn_factory() as conn:
            row = await get_backup(conn, backup_id=backup_id)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown backup",
                    "detail": backup_id,
                },
            )
        body = await download_backup_bytes(b_blobs, backup_id=backup_id)
        return PlainTextResponse(
            content=body,
            headers={"Content-Disposition": f'attachment; filename="{backup_id}.hex"'},
        )

    @router.post("/api/backups/{backup_id}/promote")
    async def promote(backup_id: str, body: _Promote) -> dict[str, Any]:
        async with conn_factory() as conn:
            backup = await get_backup(conn, backup_id=backup_id)
            if backup is None:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown backup",
                        "detail": backup_id,
                    },
                )
            try:
                hex_text = await download_backup_bytes(b_blobs, backup_id=backup_id)
            except BackupNotFound:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown backup",
                        "detail": backup_id,
                    },
                )
            test_command = backup["test_command"] if body.copy_test_pair else None
            expected_response = backup["expected_response"] if body.copy_test_pair else None
            try:
                return await create_firmware(
                    conn,
                    blobs_dir=f_blobs,
                    name=body.name,
                    description=body.description,
                    firmware=hex_text,
                    test_command=test_command,
                    expected_response=expected_response,
                    tag_ids=body.tags,
                    source_backup_id=backup_id,
                )
            except TagNotFound as exc:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "tag not found",
                        "detail": str(exc),
                    },
                )

    return router
