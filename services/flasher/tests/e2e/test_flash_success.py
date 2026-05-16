from conftest import wait_for_terminal


def test_flash_happy_path_returns_success_outcome(http) -> None:
    """POST /flash/api/flash with a firmware source returns a job_id; polling
    /api/flash/<id> eventually reports status='done' with result.outcome=success.
    """
    fid = http.post(
        "/flash/api/firmware",
        json={"name": "happy", "firmware": ":00000001FF\n"},
    ).json()["id"]

    r = http.post(
        "/flash/api/flash",
        json={
            "client": "alice_machine",
            "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
        },
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    body = wait_for_terminal(http, job_id)
    assert body["status"] == "done", body
    assert body["result"]["outcome"] == "success"

    http.delete(f"/flash/api/firmware/{fid}")


def test_flash_rejects_unknown_client(http) -> None:
    fid = http.post(
        "/flash/api/firmware",
        json={"name": "reject", "firmware": ":00000001FF\n"},
    ).json()["id"]
    r = http.post(
        "/flash/api/flash",
        json={
            "client": "nobody",
            "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
        },
    )
    assert r.status_code == 400
    assert r.json()["error"] == "unknown client"
    http.delete(f"/flash/api/firmware/{fid}")
