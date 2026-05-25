"""aiortc plumbing: peer connection factory + SDP candidate rewrite.

The streamer container sees host ICE candidates with internal Docker
addresses. We rewrite host-type candidate addresses to ``public_ip`` so
external peers (SerialHop, browsers) connect to the routable VPS address.
The host's UDP port mapping (50000-50100/udp) preserves the port unchanged.
"""

from __future__ import annotations

import re

from aiortc import RTCPeerConnection


_CANDIDATE_RE = re.compile(
    r"^(a=candidate:\S+ \d+ \S+ \d+ )(\S+)( \d+ typ host.*)$",
    flags=re.MULTILINE,
)


def parse_udp_port_range(spec: str) -> tuple[int, int]:
    """Parse "low-high" into (low, high) with low<high."""
    parts = spec.split("-")
    if len(parts) != 2:
        raise ValueError(f"udp_port_range must be 'low-high', got {spec!r}")
    low, high = int(parts[0]), int(parts[1])
    if low >= high:
        raise ValueError(f"udp_port_range low must be < high, got {spec!r}")
    return low, high


def rewrite_sdp_with_public_ip(sdp: str, *, public_ip: str) -> str:
    """Replace the address in every host-type ICE candidate with public_ip."""

    def _swap(match: re.Match[str]) -> str:
        return f"{match.group(1)}{public_ip}{match.group(3)}"

    return _CANDIDATE_RE.sub(_swap, sdp)


def new_peer_connection() -> RTCPeerConnection:
    """Fresh peer connection. ICE servers empty in v1; rewrite handles NAT."""
    return RTCPeerConnection()
