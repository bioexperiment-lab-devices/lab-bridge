from conftest import wait_for_terminal


def test_promote_backup_to_firmware(http) -> None:
    fid = http.post("/flash/api/firmware",
                    json={"name": "src", "firmware": ":00000001FF\n"}).json()["id"]
    job = http.post("/flash/api/flash", json={
        "client": "alice_machine", "port": "COM3",
        "source": {"kind": "firmware", "id": fid},
    }).json()
    wait_for_terminal(http, job["job_id"])
    bid = http.get(f"/flash/api/flash/{job['job_id']}").json()["backup_id"]

    promoted = http.post(f"/flash/api/backups/{bid}/promote", json={
        "name": "promoted-fw",
    }).json()
    assert promoted["source_backup_id"] == bid
    assert promoted["sha256"]  # bytes were cloned

    http.delete(f"/flash/api/firmware/{promoted['id']}")
    http.delete(f"/flash/api/backups/{bid}")
    http.delete(f"/flash/api/firmware/{fid}")
