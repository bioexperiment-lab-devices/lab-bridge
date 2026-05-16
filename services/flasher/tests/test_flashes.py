from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.db import connect, migrate
from app.flashes import (
    FlashNotFound,
    FlashStillRunning,
    create_running_flash,
    get_flash,
    get_running_flash,
    list_flashes,
    set_note,
    set_terminal_done,
    set_terminal_error,
)


@pytest.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "flasher.db"
    await migrate(db_path)
    async with connect(db_path) as conn:
        yield conn


def _running_payload(**over) -> dict:
    base = dict(
        client="khamit",
        port_name="COM3",
        port_snapshot={"vid": "2341", "pid": "0043", "serial_number": "", "product": "Arduino Uno"},
        source_kind="firmware",
        source_id="fw-1",
        firmware_sha256="abc",
        firmware_name="pump v3",
        test_command_used="01",
        expected_response_used="aa",
        skip_backup=False,
    )
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_create_running_flash_inserts_row(db) -> None:
    fid = await create_running_flash(db, **_running_payload())
    row = await get_flash(db, flash_id=fid)
    assert row["status"] == "running"
    assert row["client"] == "khamit"
    assert row["firmware_name"] == "pump v3"
    assert row["started_at"]


@pytest.mark.asyncio
async def test_set_terminal_done_writes_outcome_and_duration(db) -> None:
    fid = await create_running_flash(db, **_running_payload())
    await set_terminal_done(
        db,
        flash_id=fid,
        outcome="success",
        result_json='{"outcome":"success"}',
        backup_id="b-1",
        duration_ms=12345,
    )
    row = await get_flash(db, flash_id=fid)
    assert row["status"] == "done"
    assert row["outcome"] == "success"
    assert row["result_json"] == '{"outcome":"success"}'
    assert row["backup_id"] == "b-1"
    assert row["duration_ms"] == 12345
    assert row["finished_at"]


@pytest.mark.asyncio
async def test_set_terminal_error(db) -> None:
    fid = await create_running_flash(db, **_running_payload())
    await set_terminal_error(
        db,
        flash_id=fid,
        error_code="upstream unreachable",
        error_detail="connection refused",
        duration_ms=100,
    )
    row = await get_flash(db, flash_id=fid)
    assert row["status"] == "error"
    assert row["error_code"] == "upstream unreachable"


@pytest.mark.asyncio
async def test_get_unknown_returns_none(db) -> None:
    assert await get_flash(db, flash_id="no") is None


@pytest.mark.asyncio
async def test_get_running_flash_returns_most_recent(db) -> None:
    a = await create_running_flash(db, **_running_payload())
    b = await create_running_flash(db, **_running_payload())
    assert (await get_running_flash(db))["id"] == b
    await set_terminal_done(
        db, flash_id=b, outcome="success", result_json="{}", backup_id=None, duration_ms=1000
    )
    assert (await get_running_flash(db))["id"] == a


@pytest.mark.asyncio
async def test_list_flashes_with_filters(db) -> None:
    a = await create_running_flash(db, **_running_payload(client="khamit"))
    b = await create_running_flash(db, **_running_payload(client="other"))
    await set_terminal_done(
        db, flash_id=a, outcome="success", result_json="{}", backup_id=None, duration_ms=1000
    )
    await set_terminal_done(
        db, flash_id=b, outcome="failed_backup", result_json="{}", backup_id=None, duration_ms=2000
    )

    # filter by client
    page = await list_flashes(db, client=["khamit"])
    assert {x["id"] for x in page["items"]} == {a}

    # filter by outcome
    page = await list_flashes(db, outcome=["success"])
    assert {x["id"] for x in page["items"]} == {a}

    # date range — both should be included with wide range
    page = await list_flashes(db, since="2020-01-01T00:00:00Z", until="2030-01-01T00:00:00Z")
    assert len(page["items"]) == 2


@pytest.mark.asyncio
async def test_set_note_rejected_while_running(db) -> None:
    fid = await create_running_flash(db, **_running_payload())
    with pytest.raises(FlashStillRunning):
        await set_note(db, flash_id=fid, note="x")


@pytest.mark.asyncio
async def test_set_note_after_terminal(db) -> None:
    fid = await create_running_flash(db, **_running_payload())
    await set_terminal_done(
        db, flash_id=fid, outcome="success", result_json="{}", backup_id=None, duration_ms=1
    )
    await set_note(db, flash_id=fid, note="hello")
    row = await get_flash(db, flash_id=fid)
    assert row["operator_note"] == "hello"


@pytest.mark.asyncio
async def test_set_note_unknown_raises(db) -> None:
    with pytest.raises(FlashNotFound):
        await set_note(db, flash_id="no", note="x")


@pytest.fixture
def http_app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "test-token")
    # one online client wired into roster
    (tmp_path / "clients.json").write_text(
        '{"khamit": {"port": 9000, "password_sha256": ""}}', encoding="utf-8"
    )
    import importlib
    import app.main as m

    importlib.reload(m)
    with TestClient(m.app) as c:
        yield c, tmp_path


def _seed_firmware(http_app) -> str:
    client, _ = http_app
    return client.post(
        "/flash/api/firmware", json={"name": "fw", "firmware": ":00000001FF\n"}
    ).json()["id"]


def _stub_serialhop(respx_mock) -> None:
    """Match all SerialHop calls in tests; return a happy success."""
    respx_mock.post(host="chisel", port=9000, path="/devices/disconnect").mock(
        return_value=httpx.Response(200, json={"released": 0})
    )
    respx_mock.post(host="chisel", port=9000, path__regex=r"/flash/.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "outcome": "success",
                "port": "COM3",
                "stages": {"preflight": {"status": "ok"}},
            },
        )
    )


def test_post_flash_inserts_running_row(http_app) -> None:
    client, tmp_path = http_app
    fid = _seed_firmware(http_app)
    with respx.mock(assert_all_called=False) as respx_mock:
        _stub_serialhop(respx_mock)
        r = client.post(
            "/flash/api/flash",
            json={
                "client": "khamit",
                "port": "COM3",
                "source": {"kind": "firmware", "id": fid},
            },
        )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    with sqlite3.connect(tmp_path / "flasher.db") as conn:
        row = conn.execute(
            "SELECT status, source_id, firmware_name FROM flashes WHERE id = ?", (job_id,)
        ).fetchone()
    assert row[1] == fid


def test_post_flash_with_test_override_saves_back_when_flag_set(http_app) -> None:
    client, tmp_path = http_app
    fid = _seed_firmware(http_app)
    with respx.mock(assert_all_called=False) as respx_mock:
        _stub_serialhop(respx_mock)
        r = client.post(
            "/flash/api/flash",
            json={
                "client": "khamit",
                "port": "COM3",
                "source": {"kind": "firmware", "id": fid},
                "test_override": {"command": "01", "expected_response": "aa"},
                "save_test_to_record": True,
            },
        )
    assert r.status_code == 200
    # The firmware record now carries the saved test pair.
    r = client.get(f"/flash/api/firmware/{fid}")
    body = r.json()
    assert body["test_command"] == "01"
    assert body["expected_response"] == "aa"


def test_post_flash_unknown_source(http_app) -> None:
    client, _ = http_app
    r = client.post(
        "/flash/api/flash",
        json={
            "client": "khamit",
            "port": "COM3",
            "source": {"kind": "firmware", "id": "no-such"},
        },
    )
    assert r.status_code == 404
    assert r.json()["error"] == "unknown source"


def test_get_flash_current_and_by_id(http_app) -> None:
    client, _ = http_app
    fid = _seed_firmware(http_app)
    with respx.mock(assert_all_called=False) as respx_mock:
        _stub_serialhop(respx_mock)
        r = client.post(
            "/flash/api/flash",
            json={
                "client": "khamit",
                "port": "COM3",
                "source": {"kind": "firmware", "id": fid},
            },
        )
    job_id = r.json()["job_id"]
    # Poll until terminal.
    for _ in range(20):
        body = client.get(f"/flash/api/flash/{job_id}").json()
        if body.get("status") in {"done", "error"}:
            break
        time.sleep(0.05)
    assert body["status"] in {"done", "error"}


def test_http_list_flashes_with_filters(http_app) -> None:
    client, _ = http_app
    fid = _seed_firmware(http_app)
    with respx.mock(assert_all_called=False) as respx_mock:
        _stub_serialhop(respx_mock)
        for _ in range(2):
            client.post(
                "/flash/api/flash",
                json={
                    "client": "khamit",
                    "port": "COM3",
                    "source": {"kind": "firmware", "id": fid},
                },
            )
    for _ in range(20):
        body = client.get("/flash/api/flashes").json()
        if all(x["status"] in {"done", "error"} for x in body["items"]):
            break
        time.sleep(0.05)
    r = client.get("/flash/api/flashes?client=khamit")
    assert len(r.json()["items"]) == 2


def test_patch_note_rejected_while_running(http_app, tmp_path) -> None:
    client, _ = http_app
    # Hand-seed a running flash row.
    db = tmp_path / "flasher.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
            "VALUES ('jx', 'running', 'c', 'COM3', '{}', 'firmware', 'fid', 'sha', 'n', 0, '2026-01-01T00:00:00Z')"
        )
        conn.commit()
    r = client.patch("/flash/api/flashes/jx/note", json={"note": "x"})
    assert r.status_code == 400


def test_patch_note_after_terminal(http_app, tmp_path) -> None:
    client, _ = http_app
    db = tmp_path / "flasher.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, outcome, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, "
            "started_at, finished_at) "
            "VALUES ('jx', 'done', 'success', 'c', 'COM3', '{}', 'firmware', "
            "'fid', 'sha', 'n', 0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:05Z')"
        )
        conn.commit()
    r = client.patch("/flash/api/flashes/jx/note", json={"note": "hello"})
    assert r.status_code == 200
    r = client.get("/flash/api/flash/jx")
    assert r.json()["operator_note"] == "hello"


def test_replay_410_when_source_deleted(http_app, tmp_path) -> None:
    client, _ = http_app
    db = tmp_path / "flasher.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, outcome, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, "
            "test_command_used, expected_response_used, skip_backup, started_at, finished_at) "
            "VALUES ('jx', 'done', 'success', 'khamit', 'COM3', '{}', 'firmware', "
            "'gone-fid', 'sha', 'fw', NULL, NULL, 0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:05Z')"
        )
        conn.commit()
    r = client.post("/flash/api/flashes/jx/replay", json={})
    assert r.status_code == 410
    assert r.json()["error"] == "source deleted"
