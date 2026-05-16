from conftest import wait_for_terminal


def test_bulk_delete_partial_outcomes(http) -> None:
    # Build two backups by flashing two different firmwares.
    fids = []
    bids = []
    for i in range(2):
        fid = http.post("/flash/api/firmware",
                        json={"name": f"bd-{i}", "firmware": f":000000{i:02d}FF\n"}).json()["id"]
        fids.append(fid)
        job = http.post("/flash/api/flash", json={
            "client": "alice_machine", "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
        }).json()
        wait_for_terminal(http, job["job_id"])
        bids.append(http.get(f"/flash/api/flash/{job['job_id']}").json()["backup_id"])

    r = http.post("/flash/api/backups/bulk-delete",
                  json={"ids": [*bids, "no-such"]})
    body = r.json()
    assert body["deleted"] == 2
    assert any(x["id"] == "no-such" for x in body["refused"])

    for fid in fids:
        http.delete(f"/flash/api/firmware/{fid}")
