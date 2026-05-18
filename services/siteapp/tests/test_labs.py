from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.labs import LabsAggregator, _compare_versions, aggregate_labs


def _write_roster(clients_file: Path, entries: dict[str, int]) -> None:
    clients_file.write_text(
        json.dumps({name: {"port": port, "password_sha256": "00" * 32} for name, port in entries.items()}),
        encoding="utf-8",
    )


def _write_meta(agent_root: Path, version: str) -> None:
    (agent_root / "meta.json").write_text(
        json.dumps({"version": version, "size": 1, "sha256": "x", "uploaded_at": "2026-05-01T00:00:00Z"}),
        encoding="utf-8",
    )
    (agent_root / "windows").mkdir(exist_ok=True)
    (agent_root / "windows" / "agent.exe").write_bytes(b"x")


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | str):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        if isinstance(self._payload, str):
            raise ValueError("malformed json")
        return self._payload


@pytest.mark.asyncio
async def test_aggregate_all_online(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001, "bravo": 9002})
    _write_meta(site_data / "agent", "0.9.0")

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, {"version": "0.9.0", "hostname": "PC-1"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert [r["name"] for r in rows] == ["alpha", "bravo"]
    assert all(r["online"] for r in rows)
    assert all(r["version"] == "0.9.0" for r in rows)
    assert all(r["outdated"] is False for r in rows)


@pytest.mark.asyncio
async def test_aggregate_mix_online_offline(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001, "bravo": 9002})

    async def fake_get(self, url, **kwargs):
        if "9001" in str(url):
            return _FakeResponse(200, {"version": "0.9.0"})
        raise httpx.TimeoutException("timeout")

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    online = [r for r in rows if r["online"]]
    offline = [r for r in rows if not r["online"]]
    assert [r["name"] for r in online] == ["alpha"]
    assert [r["name"] for r in offline] == ["bravo"]
    assert rows[0]["name"] == "alpha"


@pytest.mark.asyncio
async def test_aggregate_malformed_json_marked_offline(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, "not json")

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows == [{"name": "alpha", "online": False}]


@pytest.mark.asyncio
async def test_aggregate_non_200_marked_offline(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(503, {})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows == [{"name": "alpha", "online": False}]


@pytest.mark.asyncio
async def test_aggregate_no_meta_omits_outdated(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, {"version": "0.5.0"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows[0]["online"] is True
    assert rows[0]["version"] == "0.5.0"
    assert "outdated" not in rows[0]


@pytest.mark.asyncio
async def test_aggregate_outdated_detected(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})
    _write_meta(site_data / "agent", "0.9.0")

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, {"version": "0.5.0"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows[0]["outdated"] is True


@pytest.mark.asyncio
async def test_aggregate_version_with_build_sha_stripped(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})
    _write_meta(site_data / "agent", "0.9.0")

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, {"version": "0.9.0+abc1234"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows[0]["outdated"] is False


@pytest.mark.asyncio
async def test_aggregate_non_pep440_no_outdated(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})
    _write_meta(site_data / "agent", "garbage")

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, {"version": "0.9.0"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows[0]["online"] is True
    assert "outdated" not in rows[0]


def test_compare_versions_basic() -> None:
    assert _compare_versions("0.5.0", "0.9.0") == "outdated"
    assert _compare_versions("0.9.0", "0.9.0") == "current"
    assert _compare_versions("1.0.0", "0.9.0") == "current"
    assert _compare_versions("0.9.0+abc", "0.9.0") == "current"
    assert _compare_versions("bad", "0.9.0") == "unknown"
    assert _compare_versions("0.9.0", "bad") == "unknown"


@pytest.mark.asyncio
async def test_cache_serves_stale_within_ttl(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})
    agg = LabsAggregator(site_data / "agent", _clients_file_default, host="chisel", ttl_seconds=60)

    call_count = 0

    async def fake_get(self, url, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(200, {"version": "0.9.0"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        await agg.list_labs()
        await agg.list_labs()

    assert call_count == 1
