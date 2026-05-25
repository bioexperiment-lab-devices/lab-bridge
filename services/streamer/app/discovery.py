"""Per-lab discovery cache for armed translations.

For each lab in the roster, the cache periodically polls
``http://chisel:<port>/api/translations`` and returns the parsed list of
TranslationDescriptors. Any failure (connection error, non-200, malformed
body) is normalized to an empty list — that lab's card grays out on the
picker. Refresh is lazy: the cache is updated on read when stale, or
explicitly on force_refresh=True.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

# Translation IDs that survive a chisel-tunneled HTTP round-trip back to
# SerialHop. The id is embedded in a URL path segment when the server calls
# /api/translations/{id}/{start,stop}, and Go's net/http (used by SerialHop)
# decodes percent-escapes before route matching — so an encoded '%2F'
# becomes a literal '/' and the single-segment pattern fails. Restricting
# the charset at discovery time gives a clear early failure instead of a
# 502 deep in the WHEP path.
#
# Spec: docs/superpowers/specs/2026-05-24-serialhop-streaming-protocol.md
# §1.1 — required charset is [A-Za-z0-9._-], max 128 chars.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranslationDescriptor:
    id: str
    label: str


@dataclass
class _CacheEntry:
    fetched_at: float
    value: list[TranslationDescriptor]


class DiscoveryCache:
    def __init__(
        self,
        *,
        roster: dict[str, int],
        chisel_host: str,
        ttl_s: float,
        request_timeout_s: float,
    ) -> None:
        self._roster = roster
        self._host = chisel_host
        self._ttl_s = ttl_s
        self._timeout_s = request_timeout_s
        self._cache: dict[str, _CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def list(
        self, lab_name: str, *, force_refresh: bool = False
    ) -> list[TranslationDescriptor]:
        if lab_name not in self._roster:
            return []
        if not force_refresh:
            entry = self._cache.get(lab_name)
            if entry is not None and time.monotonic() - entry.fetched_at < self._ttl_s:
                return entry.value
        lock = self._locks.setdefault(lab_name, asyncio.Lock())
        async with lock:
            if not force_refresh:
                entry = self._cache.get(lab_name)
                if entry is not None and time.monotonic() - entry.fetched_at < self._ttl_s:
                    return entry.value
            value = await self._fetch(lab_name)
            self._cache[lab_name] = _CacheEntry(fetched_at=time.monotonic(), value=value)
            return value

    async def _fetch(self, lab_name: str) -> list[TranslationDescriptor]:
        port = self._roster[lab_name]
        url = f"http://{self._host}:{port}/api/translations"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.get(url)
        except (httpx.HTTPError, OSError):
            return []
        if resp.status_code != 200:
            return []
        try:
            payload: Any = resp.json()
        except ValueError:
            return []
        if not isinstance(payload, dict):
            return []
        items = payload.get("translations")
        if not isinstance(items, list):
            return []
        out: list[TranslationDescriptor] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tid = item.get("id")
            label = item.get("label")
            if not isinstance(tid, str) or not isinstance(label, str):
                continue
            if not _ID_PATTERN.fullmatch(tid):
                log.warning(
                    "lab %r announced translation with unsupported id charset "
                    "(must match %r); dropping. id=%r label=%r",
                    lab_name,
                    _ID_PATTERN.pattern,
                    tid,
                    label,
                )
                continue
            out.append(TranslationDescriptor(id=tid, label=label))
        return out
