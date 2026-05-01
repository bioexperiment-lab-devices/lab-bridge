from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
from datetime import UTC, datetime

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.config import Settings

VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9.]+)?$")
MAX_AGENT_BYTES = 100 * 1024 * 1024  # 100 MiB
CHUNK = 64 * 1024


def _check_token(authorization: str | None, expected: str) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401)
    candidate = authorization.split(None, 1)[1].strip()
    if not secrets.compare_digest(candidate, expected):
        raise HTTPException(status_code=401)


async def upload_agent(
    settings: Settings,
    *,
    version: str,
    binary: UploadFile,
    authorization: str | None,
) -> dict[str, object]:
    _check_token(authorization, settings.agent_upload_token)
    if not VERSION_RE.match(version):
        raise HTTPException(status_code=400, detail="invalid version")

    agent_dir = settings.agent_root / "windows"
    tmp_dir = settings.agent_root / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    agent_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    size = 0
    fd, tmp_name = tempfile.mkstemp(dir=str(tmp_dir), prefix="agent-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await binary.read(CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_AGENT_BYTES:
                    raise HTTPException(status_code=413, detail="upload too large")
                digest.update(chunk)
                out.write(chunk)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    sha256 = digest.hexdigest()
    target = agent_dir / "agent.exe"
    os.replace(tmp_name, target)

    meta = {
        "version": version,
        "sha256": sha256,
        "uploaded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "size": size,
    }
    fd2, meta_tmp = tempfile.mkstemp(
        dir=str(settings.agent_root), prefix="meta-", suffix=".json"
    )
    with os.fdopen(fd2, "w") as f:
        json.dump(meta, f)
    os.replace(meta_tmp, settings.agent_root / "meta.json")
    return {"version": version, "sha256": sha256, "size": size}


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.post("/api/agent/upload")
    async def upload_endpoint(
        version: str = Form(...),
        binary: UploadFile = File(...),
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        return await upload_agent(
            settings, version=version, binary=binary, authorization=authorization
        )

    return router
