from __future__ import annotations


import httpx
import respx

from app.discovery import DiscoveryCache, TranslationDescriptor


def _make_cache(
    roster: dict[str, int],
    *,
    ttl_s: float = 10.0,
    request_timeout_s: float = 1.0,
) -> DiscoveryCache:
    return DiscoveryCache(
        roster=roster,
        chisel_host="chisel",
        ttl_s=ttl_s,
        request_timeout_s=request_timeout_s,
    )


@respx.mock
async def test_fetches_armed_translations_per_lab() -> None:
    respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(
            200,
            json={
                "translations": [
                    {"id": "cam-0", "label": "Side"},
                    {"id": "cam-1", "label": "Top"},
                ]
            },
        )
    )
    cache = _make_cache({"alice": 8089})

    result = await cache.list("alice")

    assert result == [
        TranslationDescriptor(id="cam-0", label="Side"),
        TranslationDescriptor(id="cam-1", label="Top"),
    ]


@respx.mock
async def test_unknown_lab_returns_empty() -> None:
    cache = _make_cache({"alice": 8089})
    assert await cache.list("ghost") == []


@respx.mock
async def test_lab_offline_returns_empty() -> None:
    respx.get("http://chisel:8089/api/translations").mock(
        side_effect=httpx.ConnectError("no tunnel")
    )
    cache = _make_cache({"alice": 8089})
    assert await cache.list("alice") == []


@respx.mock
async def test_lab_500_returns_empty() -> None:
    respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(500, text="boom")
    )
    cache = _make_cache({"alice": 8089})
    assert await cache.list("alice") == []


@respx.mock
async def test_results_cached_within_ttl() -> None:
    route = respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(
            200,
            json={"translations": [{"id": "cam-0", "label": "Side"}]},
        )
    )
    cache = _make_cache({"alice": 8089}, ttl_s=60.0)

    await cache.list("alice")
    await cache.list("alice")

    assert route.call_count == 1


@respx.mock
async def test_force_refresh_bypasses_cache() -> None:
    payloads = [
        {"translations": [{"id": "cam-0", "label": "Side"}]},
        {"translations": [{"id": "cam-0", "label": "Side"}, {"id": "cam-1", "label": "Top"}]},
    ]
    call_count = {"n": 0}

    def _handler(_request: httpx.Request) -> httpx.Response:
        idx = call_count["n"]
        call_count["n"] += 1
        return httpx.Response(200, json=payloads[min(idx, len(payloads) - 1)])

    respx.get("http://chisel:8089/api/translations").mock(side_effect=_handler)
    cache = _make_cache({"alice": 8089}, ttl_s=60.0)

    first = await cache.list("alice")
    refreshed = await cache.list("alice", force_refresh=True)

    assert len(first) == 1
    assert len(refreshed) == 2


@respx.mock
async def test_malformed_response_returns_empty() -> None:
    respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(200, text="not json")
    )
    cache = _make_cache({"alice": 8089})
    assert await cache.list("alice") == []


@respx.mock
async def test_translations_field_must_be_array() -> None:
    respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(200, json={"translations": "nope"})
    )
    cache = _make_cache({"alice": 8089})
    assert await cache.list("alice") == []


@respx.mock
async def test_translation_with_url_unsafe_id_is_dropped(caplog) -> None:
    """SerialHop bug: announcing a raw Windows DirectShow device path as the
    id (containing '/', '#', '?', '\\') breaks the control-plane round-trip
    because Go's net/http decodes percent-escapes before route matching.
    Drop such entries at discovery time with a warning instead of letting
    them propagate into a confusing 502 deep in the WHEP path."""
    import logging

    respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(
            200,
            json={
                "translations": [
                    {"id": "cam-0", "label": "Good"},
                    {"id": "@device_pnp_\\\\?\\usb#vid_1bcf", "label": "Bad"},
                    {"id": "with/slash", "label": "Also bad"},
                    {"id": "with space", "label": "Also bad"},
                    {"id": "ok.id_with-safe-chars", "label": "Also good"},
                ]
            },
        )
    )
    cache = _make_cache({"alice": 8089})

    with caplog.at_level(logging.WARNING):
        result = await cache.list("alice")
    assert {t.id for t in result} == {"cam-0", "ok.id_with-safe-chars"}
    assert sum("unsupported id charset" in r.message for r in caplog.records) == 3


@respx.mock
async def test_id_too_long_is_dropped() -> None:
    long_id = "a" * 129
    respx.get("http://chisel:8089/api/translations").mock(
        return_value=httpx.Response(
            200,
            json={"translations": [{"id": long_id, "label": "Too long"}]},
        )
    )
    cache = _make_cache({"alice": 8089})
    assert await cache.list("alice") == []
