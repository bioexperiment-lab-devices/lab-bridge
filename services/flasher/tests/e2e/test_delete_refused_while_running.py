import time


def test_delete_firmware_refused_during_in_flight_flash(http, set_stub_outcome) -> None:
    # Force a slow flash by switching the stub's outcome — we just need any row.
    # Schedule the flash and immediately attempt a delete; the stub typically
    # finishes in ~0.5s. If your stub completes faster than the test window,
    # increase its sleep via env override.
    fid = http.post(
        "/flash/api/firmware", json={"name": "race", "firmware": ":00000001FF\n"}
    ).json()["id"]
    job = http.post(
        "/flash/api/flash",
        json={
            "client": "alice_machine",
            "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
        },
    ).json()
    # Polling: while status is running, delete should be refused with 409.
    refused = False
    for _ in range(30):
        s = http.get(f"/flash/api/flash/{job['job_id']}").json().get("status")
        if s == "running":
            r = http.delete(f"/flash/api/firmware/{fid}")
            if r.status_code == 409:
                refused = True
                break
        time.sleep(0.05)
    # Wait out the flash.
    for _ in range(60):
        s = http.get(f"/flash/api/flash/{job['job_id']}").json().get("status")
        if s in {"done", "error"}:
            break
        time.sleep(0.1)
    assert refused, "expected at least one 409 while the flash was running"
    http.delete(f"/flash/api/firmware/{fid}")
