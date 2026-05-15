def test_spa_index_served_at_flash_root(http) -> None:
    r = http.get("/flash/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_spa_fallback_serves_index_for_unknown_path(http) -> None:
    """Any /flash/<anything> path that isn't a static asset returns index.html
    (standard SPA fallback). Lets the SPA own client-side routing.
    """
    r = http.get("/flash/some/deep/route")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
