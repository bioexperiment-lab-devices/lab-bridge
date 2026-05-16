from conftest import wait_for_terminal


def test_flash_from_firmware_record_writes_audit_row(http) -> None:
    fid = http.post(
        "/flash/api/firmware", json={"name": "boot", "firmware": ":00000001FF\n"}
    ).json()["id"]
    job = http.post(
        "/flash/api/flash",
        json={
            "client": "alice_machine",
            "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
        },
    ).json()
    body = wait_for_terminal(http, job["job_id"])
    assert body["status"] == "done"
    # Logs page surfaces this row.
    r = http.get("/flash/api/flashes?client=alice_machine&limit=10")
    assert any(x["id"] == job["job_id"] for x in r.json()["items"])
    http.delete(f"/flash/api/firmware/{fid}")
