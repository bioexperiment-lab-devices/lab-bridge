from __future__ import annotations

import time

import httpx
import pytest

OFFER_SDP_TEMPLATE = (
    "v=0\r\n"
    "o=- 0 0 IN IP4 127.0.0.1\r\n"
    "s=-\r\n"
    "t=0 0\r\n"
    "m=video 9 UDP/TLS/RTP/SAVPF 96\r\n"
    "c=IN IP4 0.0.0.0\r\n"
    "a=rtpmap:96 VP8/90000\r\n"
    "a=recvonly\r\n"
)


def _whep(http_streamer: httpx.Client, lab: str, tid: str) -> httpx.Response:
    return http_streamer.post(
        f"/streamer/whep/{lab}/{tid}",
        headers={"Content-Type": "application/sdp"},
        content=OFFER_SDP_TEMPLATE,
    )


def test_first_whep_triggers_serialhop_start(
    http_streamer: httpx.Client, http_stub: httpx.Client
) -> None:
    _whep(http_streamer, "alice", "cam-0")
    time.sleep(0.3)
    calls = http_stub.get("/__/calls").json()
    assert len(calls["starts"]) == 1
    assert calls["starts"][0]["tid"] == "cam-0"


def test_drain_emits_stop_after_debounce(
    http_streamer: httpx.Client, http_stub: httpx.Client
) -> None:
    resp = _whep(http_streamer, "alice", "cam-0")
    if resp.status_code != 201:
        pytest.skip("publisher did not attach; covered in test_media_flows")

    location = resp.headers["Location"]
    http_streamer.delete(location)

    time.sleep(2.0)  # debounce is 1s in e2e settings
    calls = http_stub.get("/__/calls").json()
    assert len(calls["stops"]) >= 1


def test_two_viewers_share_publisher(http_streamer: httpx.Client, http_stub: httpx.Client) -> None:
    http_stub.post("/__/reset")
    a = _whep(http_streamer, "alice", "cam-0")
    b = _whep(http_streamer, "alice", "cam-0")
    if a.status_code != 201 or b.status_code != 201:
        pytest.skip("publisher did not attach")
    time.sleep(0.3)
    calls = http_stub.get("/__/calls").json()
    assert len(calls["starts"]) == 1
