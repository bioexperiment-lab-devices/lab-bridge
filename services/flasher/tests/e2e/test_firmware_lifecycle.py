def test_create_get_patch_delete(http) -> None:
    r = http.post("/flash/api/firmware", json={"name": "fw-1", "firmware": ":00000001FF\n"})
    assert r.status_code == 200
    fid = r.json()["id"]

    r = http.get(f"/flash/api/firmware/{fid}")
    assert r.status_code == 200
    assert r.json()["name"] == "fw-1"

    r = http.patch(f"/flash/api/firmware/{fid}", json={"name": "fw-1-renamed", "description": "d"})
    assert r.status_code == 200
    assert r.json()["name"] == "fw-1-renamed"

    r = http.delete(f"/flash/api/firmware/{fid}")
    assert r.status_code == 200

    r = http.get(f"/flash/api/firmware/{fid}")
    assert r.status_code == 404


def test_download_returns_bytes(http) -> None:
    fid = http.post(
        "/flash/api/firmware",
        json={"name": "fw-2", "firmware": ":00000001FF\n", "original_filename": "fw-2.hex"},
    ).json()["id"]
    r = http.get(f"/flash/api/firmware/{fid}/download")
    assert r.status_code == 200
    assert r.text == ":00000001FF\n"
    assert "fw-2.hex" in r.headers.get("content-disposition", "")
    http.delete(f"/flash/api/firmware/{fid}")


def test_tag_lifecycle(http) -> None:
    tid = http.post("/flash/api/tags", json={"name": "e2e-pump"}).json()["id"]
    fid = http.post(
        "/flash/api/firmware",
        json={"name": "f-with-tag", "firmware": ":00000001FF\n", "tags": [tid]},
    ).json()["id"]
    body = http.get(f"/flash/api/firmware/{fid}").json()
    assert [t["name"] for t in body["tags"]] == ["e2e-pump"]
    # Deleting the tag CASCADEs to firmware_tags but leaves the firmware row.
    http.delete(f"/flash/api/tags/{tid}")
    body = http.get(f"/flash/api/firmware/{fid}").json()
    assert body["tags"] == []
    http.delete(f"/flash/api/firmware/{fid}")
