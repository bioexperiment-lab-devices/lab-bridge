import time


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

    body: dict = {}
    for _ in range(30):
        time.sleep(0.5)
        rec = http.get(f"/flash/api/flash/{job_id}")
        body = rec.json()
        if body.get("status") in {"done", "error"}:
            break
    assert body["status"] == "done", body
    assert body["result"]["outcome"] == "rolled_back_test_failed"
    assert body["result"]["test_result"]["match"] is False
