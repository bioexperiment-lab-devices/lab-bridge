def test_server_info_returns_expected_shape(http) -> None:
    r = http.get("/api/public/server-info")
    assert r.status_code == 200
    body = r.json()
    assert body["chisel"] == {"listen_port": 7000}
    assert body["version"] == "e2e-test"
    assert body["git_sha"] == "test"
    assert isinstance(body["forward_tunnels"], list)
    assert any(t["name"] == "loki" for t in body["forward_tunnels"])
