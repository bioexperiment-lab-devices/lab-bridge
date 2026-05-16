from conftest import wait_for_terminal


def test_flash_from_backup_source(http) -> None:
    # Seed a backup by first running a flash with default (success) outcome.
    fid = http.post(
        "/flash/api/firmware", json={"name": "seed", "firmware": ":00000001FF\n"}
    ).json()["id"]
    first = http.post(
        "/flash/api/flash",
        json={
            "client": "alice_machine",
            "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
        },
    ).json()
    wait_for_terminal(http, first["job_id"])
    backup_id = http.get(f"/flash/api/flash/{first['job_id']}").json()["backup_id"]
    assert backup_id is not None

    # Flash from the captured backup.
    second = http.post(
        "/flash/api/flash",
        json={
            "client": "alice_machine",
            "port": "COM3",
            "source": {"kind": "backup", "id": backup_id},
        },
    ).json()
    body = wait_for_terminal(http, second["job_id"])
    assert body["status"] == "done"

    http.delete(f"/flash/api/firmware/{fid}")
