from conftest import wait_for_terminal


def test_logs_filter_by_client_and_outcome(http) -> None:
    fid = http.post("/flash/api/firmware",
                    json={"name": "logs", "firmware": ":00000001FF\n"}).json()["id"]
    job = http.post("/flash/api/flash", json={
        "client": "alice_machine", "port": "COM3",
        "source": {"kind": "firmware", "id": fid},
    }).json()
    wait_for_terminal(http, job["job_id"])

    r = http.get("/flash/api/flashes?client=alice_machine&outcome=success")
    body = r.json()
    assert any(x["id"] == job["job_id"] for x in body["items"])

    # A bogus client filters everything out.
    r = http.get("/flash/api/flashes?client=__no_such_client__")
    assert r.json()["items"] == []

    http.delete(f"/flash/api/firmware/{fid}")
