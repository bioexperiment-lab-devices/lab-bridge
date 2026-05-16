from conftest import wait_for_terminal


def test_flash_returns_rolled_back_outcome_when_stub_rolls_back(http, set_stub_outcome) -> None:
    set_stub_outcome("rolled_back_test_failed")

    fid = http.post(
        "/flash/api/firmware",
        json={
            "name": "rollback-fixture",
            "firmware": ":00000001FF\n",
            "test_command": "010203",
            "expected_response": "aabbcc",
        },
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
    assert body["result"]["outcome"] == "rolled_back_test_failed"
    assert body["result"]["test_result"]["match"] is False

    http.delete(f"/flash/api/firmware/{fid}")
