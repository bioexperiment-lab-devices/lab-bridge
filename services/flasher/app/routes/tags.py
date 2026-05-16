from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import Settings
from app.tags import (
    DuplicateTagName,
    TagNotFound,
    create_tag,
    delete_tag,
    list_tags,
    rename_tag,
)


class _TagPost(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class _TagPatch(BaseModel):
    name: str = Field(min_length=1, max_length=128)


def make_router(settings: Settings, conn_factory) -> APIRouter:
    router = APIRouter()

    @router.get("/api/tags")
    async def get_all() -> dict[str, Any]:
        async with conn_factory() as conn:
            return {"items": await list_tags(conn)}

    @router.post("/api/tags")
    async def post(body: _TagPost) -> dict[str, Any]:
        async with conn_factory() as conn:
            try:
                return await create_tag(conn, name=body.name)
            except DuplicateTagName:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "name in use",
                        "detail": body.name,
                    },
                )

    @router.patch("/api/tags/{tag_id}")
    async def patch(tag_id: str, body: _TagPatch) -> dict[str, Any]:
        async with conn_factory() as conn:
            try:
                await rename_tag(conn, tag_id=tag_id, name=body.name)
            except TagNotFound:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown tag",
                        "detail": tag_id,
                    },
                )
            except DuplicateTagName:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "name in use",
                        "detail": body.name,
                    },
                )
            tags = await list_tags(conn)
            for t in tags:
                if t["id"] == tag_id:
                    return t
            raise HTTPException(status_code=500, detail={"error": "internal", "detail": ""})

    @router.delete("/api/tags/{tag_id}")
    async def delete(tag_id: str) -> dict[str, str]:
        async with conn_factory() as conn:
            try:
                await delete_tag(conn, tag_id=tag_id)
            except TagNotFound:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "unknown tag",
                        "detail": tag_id,
                    },
                )
        return {"status": "deleted"}

    return router
