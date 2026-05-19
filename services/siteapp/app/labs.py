from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Literal, TypedDict

import httpx
from fastapi import APIRouter

from app.agent import load_meta
from app.clients import load_roster
from app.config import Settings


class LabRow(TypedDict, total=False):
    name: str
    online: bool
    version: str
    hostname: str
    outdated: bool


AGENT_INFO_PATH = "/agent/info"
HTTP_TIMEOUT_SECONDS = 0.8
DEFAULT_CACHE_TTL_SECONDS = 60
CHISEL_HOST = "chisel"


def _compare_versions(lab: str, latest: str) -> Literal["outdated", "current", "unknown"]:
    """Strip +build_sha and compare with packaging.version.

    Returns 'outdated' iff lab < latest. 'unknown' on parse failure either side
    (caller should omit the outdated field entirely).
    """
    from packaging.version import InvalidVersion, Version

    def _strip(v: str) -> str:
        return v.split("+", 1)[0]

    try:
        lab_v = Version(_strip(lab))
        latest_v = Version(_strip(latest))
    except InvalidVersion:
        return "unknown"
    return "outdated" if lab_v < latest_v else "current"


async def _probe_one(
    client: httpx.AsyncClient, name: str, host: str, port: int, latest: str | None
) -> LabRow:
    """Best-effort GET /agent/info; any failure → online=False."""
    url = f"http://{host}:{port}{AGENT_INFO_PATH}"
    try:
        resp = await client.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    except (httpx.HTTPError, OSError):
        return {"name": name, "online": False}
    if resp.status_code != 200:
        return {"name": name, "online": False}
    try:
        payload = resp.json()
    except (ValueError, json.JSONDecodeError):
        return {"name": name, "online": False}
    if not isinstance(payload, dict):
        return {"name": name, "online": False}

    row: LabRow = {"name": name, "online": True}
    version = payload.get("version")
    if isinstance(version, str):
        row["version"] = version
    hostname = payload.get("hostname")
    if isinstance(hostname, str) and hostname:
        row["hostname"] = hostname

    if latest is not None and "version" in row:
        result = _compare_versions(row["version"], latest)
        if result != "unknown":
            row["outdated"] = result == "outdated"
    return row


def _sort_key(row: LabRow) -> tuple[int, str]:
    return (0 if row["online"] else 1, row["name"].lower())


class LabsAggregator:
    """Process-local cache + lock around aggregate_labs."""

    def __init__(
        self,
        agent_root: Path,
        clients_file: Path,
        *,
        host: str = CHISEL_HOST,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._agent_root = agent_root
        self._clients_file = clients_file
        self._host = host
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._cache_at: float = 0.0
        self._cache_value: list[LabRow] = []

    async def list_labs(self) -> list[LabRow]:
        now = time.monotonic()
        if self._cache_value and now - self._cache_at < self._ttl:
            return self._cache_value
        async with self._lock:
            now = time.monotonic()
            if self._cache_value and now - self._cache_at < self._ttl:
                return self._cache_value
            rows = await aggregate_labs(self._agent_root, self._clients_file, host=self._host)
            self._cache_at = now
            self._cache_value = rows
            return rows


async def aggregate_labs(
    agent_root: Path, clients_file: Path, *, host: str = CHISEL_HOST
) -> list[LabRow]:
    """Fan out to every roster lab's /agent/info; return sorted list."""
    try:
        roster = load_roster(clients_file)
    except (OSError, ValueError):
        return []

    meta = load_meta(agent_root)
    latest = meta.version if meta is not None else None

    async with httpx.AsyncClient() as client:
        tasks = [
            _probe_one(client, name, host, int(entry["port"]), latest)
            for name, entry in roster.items()
        ]
        rows: list[LabRow] = list(await asyncio.gather(*tasks)) if tasks else []

    rows.sort(key=_sort_key)
    return rows


def make_router(settings: Settings, *, host: str = CHISEL_HOST) -> APIRouter:
    """Create the /api/public/labs router with a process-local aggregator."""
    router = APIRouter()
    aggregator = LabsAggregator(settings.agent_root, settings.clients_file, host=host)

    @router.get("/api/public/labs")
    async def list_labs() -> list[LabRow]:
        return await aggregator.list_labs()

    return router
