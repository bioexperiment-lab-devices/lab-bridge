from __future__ import annotations

import pytest

from app.sfu import (
    parse_udp_port_range,
    rewrite_sdp_with_public_ip,
)


def test_parse_udp_port_range() -> None:
    assert parse_udp_port_range("50000-50100") == (50000, 50100)


def test_parse_udp_port_range_rejects_single() -> None:
    with pytest.raises(ValueError):
        parse_udp_port_range("50000")


def test_parse_udp_port_range_rejects_inverted() -> None:
    with pytest.raises(ValueError):
        parse_udp_port_range("50100-50000")


def test_rewrite_sdp_replaces_internal_candidate_addresses() -> None:
    sdp = (
        "v=0\r\n"
        "a=candidate:1 1 udp 1 172.18.0.3 50001 typ host\r\n"
        "a=candidate:2 1 udp 1 192.168.10.5 50002 typ host\r\n"
    )
    out = rewrite_sdp_with_public_ip(sdp, public_ip="1.2.3.4")
    assert "172.18.0.3" not in out
    assert "192.168.10.5" not in out
    assert "1.2.3.4 50001" in out
    assert "1.2.3.4 50002" in out


def test_rewrite_sdp_leaves_non_candidate_lines_intact() -> None:
    sdp = (
        "v=0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\na=candidate:1 1 udp 1 10.0.0.1 50001 typ host\r\n"
    )
    out = rewrite_sdp_with_public_ip(sdp, public_ip="1.2.3.4")
    assert "v=0\r\n" in out
    assert "m=video 9 UDP/TLS/RTP/SAVPF 96\r\n" in out
