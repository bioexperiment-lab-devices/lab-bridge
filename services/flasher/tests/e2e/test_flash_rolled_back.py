from conftest import wait_for_terminal


VALID_FIRMWARE_HEX = ":100000000C9461000C947E000C947E000C947E0099\n:00000001FF\n"


def test_flash_returns_rolled_back_outcome_when_stub_rolls_back(http, set_stub_outcome) -> None:
    set_stub_outcome("rolled_back_test_failed")

    r = http.post(
        "/flash/api/flash",
        json={
            "client": "alice_machine",
            "port": "COM3",
            "firmware": VALID_FIRMWARE_HEX,
            "test": {"command": "010203", "expected_response": "aabbcc"},
        },
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    body = wait_for_terminal(http, job_id)
    assert body["status"] == "done", body
    assert body["result"]["outcome"] == "rolled_back_test_failed"
    assert body["result"]["test_result"]["match"] is False
