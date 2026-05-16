def test_bearer_post_succeeds(http, bearer_headers) -> None:
    r = http.post(
        "/flash/api/v1/firmware",
        json={"name": "ci-1", "firmware": ":00000001FF\n"},
        headers=bearer_headers,
    )
    assert r.status_code == 200
    fid = r.json()["id"]
    sha = r.json()["sha256"]
    # Idempotency probe finds it.
    r = http.get(f"/flash/api/v1/firmware?sha256={sha}", headers=bearer_headers)
    assert r.status_code == 200
    assert r.json()["id"] == fid
    http.delete(f"/flash/api/firmware/{fid}")


def test_bearer_missing_token_401(http) -> None:
    r = http.post("/flash/api/v1/firmware", json={"name": "x", "firmware": ":00000001FF\n"})
    assert r.status_code == 401
    assert r.json()["error"] == "bearer required"


def test_bearer_wrong_token_401(http) -> None:
    r = http.post(
        "/flash/api/v1/firmware",
        json={"name": "x", "firmware": ":00000001FF\n"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401
    assert r.json()["error"] == "bearer invalid"
