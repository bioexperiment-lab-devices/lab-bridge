import time


VALID_FIRMWARE_HEX = ":100000000C9461000C947E000C947E000C947E0099\n:00000001FF\n"


def test_flash_happy_path_returns_success_outcome(http) -> None:
    """POST /flash/api/flash returns a job_id; polling /api/flash/<id>
    eventually returns a record whose result.outcome is 'success'.

    Note: JobStore._snapshot() uses 'status' (not 'state') with terminal
    values 'done' and 'error'.
    """
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
    assert job_id

    # Poll for completion (stub responds quickly, but flasher's state
    # machine has its own bookkeeping).
    body: dict = {}
    for _ in range(30):
        time.sleep(0.5)
        rec = http.get(f"/flash/api/flash/{job_id}")
        assert rec.status_code == 200
        body = rec.json()
        if body.get("status") in {"done", "error"}:
            break
    assert body["status"] == "done", body
    assert body["result"]["outcome"] == "success"


def test_flash_rejects_empty_firmware(http) -> None:
    r = http.post(
        "/flash/api/flash",
        json={"client": "alice_machine", "port": "COM3", "firmware": ""},
    )
    assert r.status_code == 400


def test_flash_rejects_unknown_client(http) -> None:
    r = http.post(
        "/flash/api/flash",
        json={"client": "nobody", "port": "COM3", "firmware": VALID_FIRMWARE_HEX},
    )
    assert r.status_code == 400
