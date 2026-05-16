from conftest import wait_for_terminal


def test_replay_returns_410_after_source_deleted(http) -> None:
    fid = http.post(
        "/flash/api/firmware", json={"name": "ephemeral", "firmware": ":00000001FF\n"}
    ).json()["id"]
    job = http.post(
        "/flash/api/flash",
        json={
            "client": "alice_machine",
            "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
        },
    ).json()
    wait_for_terminal(http, job["job_id"])
    http.delete(f"/flash/api/firmware/{fid}")
    r = http.post(f"/flash/api/flashes/{job['job_id']}/replay", json={})
    assert r.status_code == 410
    assert r.json()["error"] == "source deleted"
