def test_health_returns_chisel_status(http) -> None:
    """/api/public/health probes chisel:7000/health. In the harness chisel
    is not running, so we accept either ok (unlikely) or down (expected).
    What we're testing: the route exists, is unauthenticated, returns 200.
    """
    r = http.get("/api/public/health")
    assert r.status_code == 200
    body = r.json()
    assert "chisel" in body
    assert body["chisel"] in {"ok", "down"}


def test_healthz_returns_200(http) -> None:
    r = http.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
