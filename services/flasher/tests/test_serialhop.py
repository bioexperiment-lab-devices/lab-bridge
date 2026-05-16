from __future__ import annotations

import httpx
import pytest

from app.serialhop import (
    SerialHopClient,
    UpstreamUnreachable,
    UpstreamErrorResponse,
)


class _MockTransport(httpx.MockTransport):
    pass


def _make_client(handler) -> SerialHopClient:
    transport = _MockTransport(handler)
    return SerialHopClient(host="chisel", port=8089, transport=transport)


@pytest.mark.asyncio
async def test_get_ports_returns_serialhop_body() -> None:
    body = {"ports": [{"name": "COM3", "is_usb": True}]}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/serial/ports/detailed"
        return httpx.Response(200, json=body)

    client = _make_client(handler)
    assert await client.get_ports_detailed() == body


@pytest.mark.asyncio
async def test_get_ports_raises_upstream_unreachable_on_connect_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _make_client(handler)
    with pytest.raises(UpstreamUnreachable, match="connection refused"):
        await client.get_ports_detailed()


@pytest.mark.asyncio
async def test_disconnect_port_sends_port_query() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/devices/disconnect"
        assert request.url.params["port"] == "COM3"
        return httpx.Response(200, json={"released": 1})

    client = _make_client(handler)
    assert await client.disconnect_port("COM3") == {"released": 1}


@pytest.mark.asyncio
async def test_flash_sends_serialhop_shaped_body() -> None:
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen["path"] = request.url.path
        seen["body"] = _json.loads(request.content)
        return httpx.Response(
            200,
            json={"outcome": "success", "port": "COM3", "stages": {}},
        )

    client = _make_client(handler)
    out = await client.flash(
        port="COM3",
        firmware=":00000001FF\n",
        test_command="010203",
        expected_response="aabbcc",
    )
    assert seen["path"] == "/flash/COM3"
    assert seen["body"]["firmware"] == ":00000001FF\n"
    assert seen["body"]["test_command"] == "010203"
    assert seen["body"]["expected_response"] == "aabbcc"
    assert out["outcome"] == "success"


@pytest.mark.asyncio
async def test_flash_omits_test_when_not_provided() -> None:
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen["body"] = _json.loads(request.content)
        return httpx.Response(200, json={"outcome": "success", "port": "COM3", "stages": {}})

    client = _make_client(handler)
    await client.flash(port="COM3", firmware=":00000001FF\n")
    assert "test_command" not in seen["body"]
    assert "expected_response" not in seen["body"]


@pytest.mark.asyncio
async def test_flash_omits_skip_backup_by_default() -> None:
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen["body"] = _json.loads(request.content)
        return httpx.Response(200, json={"outcome": "success", "port": "COM3", "stages": {}})

    client = _make_client(handler)
    await client.flash(port="COM3", firmware=":00000001FF\n")
    assert "skip_backup" not in seen["body"]


@pytest.mark.asyncio
async def test_flash_forwards_skip_backup_when_true() -> None:
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen["body"] = _json.loads(request.content)
        return httpx.Response(200, json={"outcome": "success", "port": "COM3", "stages": {}})

    client = _make_client(handler)
    await client.flash(port="COM3", firmware=":00000001FF\n", skip_backup=True)
    assert seen["body"]["skip_backup"] is True


@pytest.mark.asyncio
async def test_flash_omits_skip_backup_when_false() -> None:
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen["body"] = _json.loads(request.content)
        return httpx.Response(200, json={"outcome": "success", "port": "COM3", "stages": {}})

    client = _make_client(handler)
    await client.flash(port="COM3", firmware=":00000001FF\n", skip_backup=False)
    # SerialHop's default is to back up, so omitting the field is the right
    # wire-level encoding when the caller didn't explicitly ask to skip.
    assert "skip_backup" not in seen["body"]


@pytest.mark.asyncio
async def test_flash_rejects_asymmetric_test_pair() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"outcome": "success", "port": "COM3", "stages": {}})

    client = _make_client(handler)
    with pytest.raises(ValueError, match="both be set or both omitted"):
        await client.flash(port="COM3", firmware=":00000001FF\n", test_command="010203")
    with pytest.raises(ValueError, match="both be set or both omitted"):
        await client.flash(port="COM3", firmware=":00000001FF\n", expected_response="aabbcc")


@pytest.mark.asyncio
async def test_flash_raises_on_4xx_with_error_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "flashing disabled", "detail": "off"})

    client = _make_client(handler)
    with pytest.raises(UpstreamErrorResponse) as exc:
        await client.flash(port="COM3", firmware=":00000001FF\n")
    assert exc.value.error_code == "flashing disabled"
    assert exc.value.detail == "off"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_flash_raises_upstream_error_on_5xx() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = _make_client(handler)
    with pytest.raises(UpstreamErrorResponse) as exc:
        await client.flash(port="COM3", firmware=":00000001FF\n")
    assert exc.value.error_code == "upstream error"
    assert exc.value.status_code == 500
