from __future__ import annotations

import httpx
import pytest
import respx

from app.control import (
    CameraBusy,
    ControlError,
    ControlPlaneClient,
    StartResult,
    UnknownTranslation,
)


def _client(roster: dict[str, int]) -> ControlPlaneClient:
    return ControlPlaneClient(
        roster=roster,
        chisel_host="chisel",
        request_timeout_s=2.0,
    )


@respx.mock
async def test_start_202_returns_started() -> None:
    route = respx.post("http://chisel:8089/api/translations/cam-0/start").mock(
        return_value=httpx.Response(202, json={})
    )
    result = await _client({"alice": 8089}).start(
        lab_name="alice",
        translation_id="cam-0",
        session_id="01ABC",
        whip_url="https://lab/streamer/whip/01ABC",
        whip_token="tk_xyz",
    )
    assert isinstance(result, StartResult)
    assert result.session_id == "01ABC"
    assert route.called
    req = route.calls[0].request
    body = httpx.Response(200, content=req.content).json()
    assert body == {
        "session_id": "01ABC",
        "whip_url": "https://lab/streamer/whip/01ABC",
        "whip_token": "tk_xyz",
        "ice_servers": [],
    }


@respx.mock
async def test_start_404_raises_unknown_translation() -> None:
    respx.post("http://chisel:8089/api/translations/ghost/start").mock(
        return_value=httpx.Response(404, json={"error": "unknown translation"})
    )
    with pytest.raises(UnknownTranslation):
        await _client({"alice": 8089}).start(
            lab_name="alice",
            translation_id="ghost",
            session_id="01",
            whip_url="https://lab/streamer/whip/01",
            whip_token="tk",
        )


@respx.mock
async def test_start_503_raises_camera_busy() -> None:
    respx.post("http://chisel:8089/api/translations/cam-0/start").mock(
        return_value=httpx.Response(503, json={"error": "camera busy"})
    )
    with pytest.raises(CameraBusy):
        await _client({"alice": 8089}).start(
            lab_name="alice",
            translation_id="cam-0",
            session_id="01",
            whip_url="https://lab/streamer/whip/01",
            whip_token="tk",
        )


@respx.mock
async def test_start_connection_error_raises_control_error() -> None:
    respx.post("http://chisel:8089/api/translations/cam-0/start").mock(
        side_effect=httpx.ConnectError("no tunnel")
    )
    with pytest.raises(ControlError):
        await _client({"alice": 8089}).start(
            lab_name="alice",
            translation_id="cam-0",
            session_id="01",
            whip_url="https://lab/streamer/whip/01",
            whip_token="tk",
        )


@respx.mock
async def test_start_unknown_lab_raises_control_error() -> None:
    with pytest.raises(ControlError, match="unknown lab"):
        await _client({"alice": 8089}).start(
            lab_name="ghost",
            translation_id="cam-0",
            session_id="01",
            whip_url="https://lab/streamer/whip/01",
            whip_token="tk",
        )


@respx.mock
async def test_stop_204_returns_silently() -> None:
    route = respx.post("http://chisel:8089/api/translations/cam-0/stop").mock(
        return_value=httpx.Response(204)
    )
    await _client({"alice": 8089}).stop(lab_name="alice", translation_id="cam-0", session_id="01")
    assert route.called
    body = httpx.Response(200, content=route.calls[0].request.content).json()
    assert body == {"session_id": "01"}


@respx.mock
async def test_stop_409_returns_silently() -> None:
    # Stale stop is the server's problem; SerialHop ignoring it is correct.
    respx.post("http://chisel:8089/api/translations/cam-0/stop").mock(
        return_value=httpx.Response(409, json={"active_session_id": "02"})
    )
    await _client({"alice": 8089}).stop(lab_name="alice", translation_id="cam-0", session_id="01")


@respx.mock
async def test_stop_connection_error_is_swallowed() -> None:
    # Best-effort: if the lab is gone, we can't reach it anyway.
    respx.post("http://chisel:8089/api/translations/cam-0/stop").mock(
        side_effect=httpx.ConnectError("no tunnel")
    )
    await _client({"alice": 8089}).stop(lab_name="alice", translation_id="cam-0", session_id="01")
