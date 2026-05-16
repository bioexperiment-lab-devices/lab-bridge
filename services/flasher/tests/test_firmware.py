from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import connect, migrate
from app.firmware import (
    FirmwareInUse,
    FirmwareNotFound,
    create_firmware,
    delete_firmware,
    download_firmware_bytes,
    get_firmware,
    list_firmware,
    update_firmware,
)
from app.tags import create_tag


@pytest.fixture
async def ctx(tmp_path: Path):
    db_path = tmp_path / "flasher.db"
    blobs_dir = tmp_path / "blobs" / "firmware"
    blobs_dir.mkdir(parents=True)
    await migrate(db_path)
    async with connect(db_path) as conn:
        yield {"conn": conn, "blobs_dir": blobs_dir}


@pytest.mark.asyncio
async def test_create_firmware_writes_row_and_blob(ctx) -> None:
    hex_text = ":00000001FF\n"
    row = await create_firmware(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        name="pump v3",
        description="desc",
        firmware=hex_text,
        test_command="01",
        expected_response="aa",
        original_filename="pump.hex",
        tag_ids=[],
    )
    assert row["name"] == "pump v3"
    assert row["sha256"] == hashlib.sha256(hex_text.encode()).hexdigest()
    assert row["size_bytes"] == len(hex_text.encode())
    assert row["original_filename"] == "pump.hex"
    assert row["tags"] == []
    blob = ctx["blobs_dir"] / f"{row['id']}.hex"
    assert blob.read_text() == hex_text


@pytest.mark.asyncio
async def test_create_firmware_with_tags(ctx) -> None:
    a = await create_tag(ctx["conn"], name="pump")
    b = await create_tag(ctx["conn"], name="prod")
    row = await create_firmware(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        name="f",
        firmware=":00000001FF\n",
        tag_ids=[a["id"], b["id"]],
    )
    names = {t["name"] for t in row["tags"]}
    assert names == {"pump", "prod"}


@pytest.mark.asyncio
async def test_get_firmware_returns_full_row(ctx) -> None:
    created = await create_firmware(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        name="x",
        firmware=":00000001FF\n",
        tag_ids=[],
    )
    got = await get_firmware(ctx["conn"], firmware_id=created["id"])
    assert got["id"] == created["id"]
    assert got["stats"] == {
        "total": 0,
        "successes": 0,
        "rollbacks": 0,
        "failures": 0,
        "last_flashed_at": None,
        "last_flashed_client": None,
        "last_flashed_port": None,
    }


@pytest.mark.asyncio
async def test_get_unknown_returns_none(ctx) -> None:
    assert await get_firmware(ctx["conn"], firmware_id="no") is None


@pytest.mark.asyncio
async def test_list_firmware_pagination_and_tag_filter(ctx) -> None:
    a = await create_tag(ctx["conn"], name="pump")
    await create_firmware(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        name="aa",
        firmware=":00000001FF\n",
        tag_ids=[a["id"]],
    )
    await create_firmware(
        ctx["conn"], blobs_dir=ctx["blobs_dir"], name="bb", firmware=":00000001FE\n", tag_ids=[]
    )

    page = await list_firmware(ctx["conn"], limit=10)
    assert len(page["items"]) == 2

    filtered = await list_firmware(ctx["conn"], tag_ids=[a["id"]])
    assert [x["name"] for x in filtered["items"]] == ["aa"]


@pytest.mark.asyncio
async def test_update_firmware_mutates_fields_and_tags(ctx) -> None:
    a = await create_tag(ctx["conn"], name="pump")
    row = await create_firmware(
        ctx["conn"], blobs_dir=ctx["blobs_dir"], name="x", firmware=":00000001FF\n", tag_ids=[]
    )
    updated = await update_firmware(
        ctx["conn"],
        firmware_id=row["id"],
        name="y",
        description="d",
        test_command="03",
        expected_response="bb",
        tag_ids=[a["id"]],
    )
    assert updated["name"] == "y"
    assert updated["description"] == "d"
    assert updated["test_command"] == "03"
    assert [t["name"] for t in updated["tags"]] == ["pump"]


@pytest.mark.asyncio
async def test_update_unknown_raises(ctx) -> None:
    with pytest.raises(FirmwareNotFound):
        await update_firmware(ctx["conn"], firmware_id="no", name="x")


@pytest.mark.asyncio
async def test_delete_firmware_removes_row_blob_and_tags(ctx) -> None:
    a = await create_tag(ctx["conn"], name="pump")
    row = await create_firmware(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        name="x",
        firmware=":00000001FF\n",
        tag_ids=[a["id"]],
    )
    await delete_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"], firmware_id=row["id"])
    assert await get_firmware(ctx["conn"], firmware_id=row["id"]) is None
    assert not (ctx["blobs_dir"] / f"{row['id']}.hex").exists()
    cur = await ctx["conn"].execute("SELECT COUNT(*) FROM firmware_tags")
    assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_delete_refuses_when_running_flash_references(ctx) -> None:
    row = await create_firmware(
        ctx["conn"], blobs_dir=ctx["blobs_dir"], name="x", firmware=":00000001FF\n", tag_ids=[]
    )
    await ctx["conn"].execute(
        "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
        "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
        "VALUES ('j1', 'running', 'c', 'COM3', '{}', 'firmware', ?, 'sha', 'x', 0, '2026-01-01T00:00:00Z')",
        (row["id"],),
    )
    await ctx["conn"].commit()
    with pytest.raises(FirmwareInUse):
        await delete_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"], firmware_id=row["id"])
    # row still exists
    assert await get_firmware(ctx["conn"], firmware_id=row["id"]) is not None


@pytest.mark.asyncio
async def test_download_firmware_bytes(ctx) -> None:
    row = await create_firmware(
        ctx["conn"], blobs_dir=ctx["blobs_dir"], name="x", firmware=":00000001FF\n", tag_ids=[]
    )
    data = await download_firmware_bytes(ctx["blobs_dir"], firmware_id=row["id"])
    assert data == ":00000001FF\n"


@pytest.fixture
def http_app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "test-token")
    (tmp_path / "clients.json").write_text("{}", encoding="utf-8")
    import importlib
    import app.main as m

    importlib.reload(m)
    with TestClient(m.app) as c:
        yield c


def test_post_firmware_creates_record(http_app: TestClient) -> None:
    r = http_app.post(
        "/flash/api/firmware",
        json={
            "name": "pump v3",
            "firmware": ":00000001FF\n",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "pump v3"
    assert body["sha256"]
    assert body["size_bytes"] > 0


def test_post_firmware_rejects_empty_firmware(http_app: TestClient) -> None:
    r = http_app.post("/flash/api/firmware", json={"name": "x", "firmware": ""})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid request"


def test_post_firmware_rejects_oversize(http_app: TestClient) -> None:
    big = "A" * (256 * 1024 + 1)
    r = http_app.post("/flash/api/firmware", json={"name": "x", "firmware": big})
    assert r.status_code == 400
    assert "exceeds" in r.json()["detail"]


def test_get_firmware_returns_one(http_app: TestClient) -> None:
    r = http_app.post("/flash/api/firmware", json={"name": "x", "firmware": ":00000001FF\n"})
    fid = r.json()["id"]
    r = http_app.get(f"/flash/api/firmware/{fid}")
    assert r.status_code == 200
    assert r.json()["id"] == fid


def test_get_firmware_404(http_app: TestClient) -> None:
    r = http_app.get("/flash/api/firmware/no-such-id")
    assert r.status_code == 404


def test_list_firmware_paginates(http_app: TestClient) -> None:
    for i in range(3):
        http_app.post(
            "/flash/api/firmware", json={"name": f"name-{i}", "firmware": f":000000{i:02d}FF\n"}
        )
    r = http_app.get("/flash/api/firmware?limit=2")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["next_before"]


def test_patch_firmware_updates_fields(http_app: TestClient) -> None:
    fid = http_app.post(
        "/flash/api/firmware", json={"name": "x", "firmware": ":00000001FF\n"}
    ).json()["id"]
    r = http_app.patch(f"/flash/api/firmware/{fid}", json={"name": "y", "description": "d"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "y"
    assert body["description"] == "d"


def test_delete_firmware_succeeds(http_app: TestClient) -> None:
    fid = http_app.post(
        "/flash/api/firmware", json={"name": "x", "firmware": ":00000001FF\n"}
    ).json()["id"]
    r = http_app.delete(f"/flash/api/firmware/{fid}")
    assert r.status_code == 200
    r = http_app.get(f"/flash/api/firmware/{fid}")
    assert r.status_code == 404


def test_delete_firmware_409_when_running_flash_references(http_app: TestClient, tmp_path) -> None:
    fid = http_app.post(
        "/flash/api/firmware", json={"name": "x", "firmware": ":00000001FF\n"}
    ).json()["id"]
    import sqlite3

    db = tmp_path / "flasher.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
            "VALUES ('jx', 'running', 'c', 'COM3', '{}', 'firmware', ?, 'sha', 'x', 0, '2026-01-01T00:00:00Z')",
            (fid,),
        )
        conn.commit()
    r = http_app.delete(f"/flash/api/firmware/{fid}")
    assert r.status_code == 409
    assert r.json()["error"] == "cannot delete: flash in flight"


def test_download_firmware(http_app: TestClient) -> None:
    fid = http_app.post(
        "/flash/api/firmware",
        json={"name": "x", "firmware": ":00000001FF\n", "original_filename": "x.hex"},
    ).json()["id"]
    r = http_app.get(f"/flash/api/firmware/{fid}/download")
    assert r.status_code == 200
    assert r.text == ":00000001FF\n"
    assert "x.hex" in r.headers.get("content-disposition", "")


def test_bearer_post_requires_token(http_app: TestClient) -> None:
    r = http_app.post("/flash/api/v1/firmware", json={"name": "x", "firmware": ":00000001FF\n"})
    assert r.status_code == 401
    assert r.json()["error"] == "bearer required"


def test_bearer_post_wrong_token(http_app: TestClient) -> None:
    r = http_app.post(
        "/flash/api/v1/firmware",
        json={"name": "x", "firmware": ":00000001FF\n"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401
    assert r.json()["error"] == "bearer invalid"


def test_bearer_post_succeeds(http_app: TestClient) -> None:
    r = http_app.post(
        "/flash/api/v1/firmware",
        json={"name": "x", "firmware": ":00000001FF\n"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "x"


def test_bearer_get_by_sha256(http_app: TestClient) -> None:
    posted = http_app.post(
        "/flash/api/v1/firmware",
        json={"name": "x", "firmware": ":00000001FF\n"},
        headers={"Authorization": "Bearer test-token"},
    ).json()
    r = http_app.get(
        f"/flash/api/v1/firmware?sha256={posted['sha256']}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 200
    assert r.json()["id"] == posted["id"]

    r = http_app.get(
        "/flash/api/v1/firmware?sha256=deadbeef", headers={"Authorization": "Bearer test-token"}
    )
    assert r.status_code == 404
