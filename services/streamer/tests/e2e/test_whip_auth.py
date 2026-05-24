from __future__ import annotations

import httpx


def test_whip_unknown_session_404() -> None:
    r = httpx.post(
        "http://127.0.0.1:8080/streamer/whip/01NOPE",
        headers={"Authorization": "Bearer tk_xyz", "Content-Type": "application/sdp"},
        content="v=0\r\n",
        timeout=5.0,
    )
    assert r.status_code == 404
