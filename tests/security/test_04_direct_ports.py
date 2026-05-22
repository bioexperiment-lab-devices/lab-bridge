"""Class 7 — direct-port exposure on the VPS.

Uses raw sockets to probe ports that should be docker-network-only. A
successful TCP connect to e.g. :2019 (Caddy admin) is a Critical finding.
"""

from __future__ import annotations

import socket

import httpx
import pytest

from conftest import Finding


INTERNAL_PORTS = [
    (2019, "Caddy admin API"),
    (9091, "Authelia"),
    (3000, "Grafana"),
    (8000, "siteapp/flasher uvicorn"),
    (8888, "JupyterLab"),
    (3100, "Loki"),
    (9090, "Prometheus"),
    (9100, "node-exporter"),
    (8080, "cadvisor"),
]


def _tcp_open(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.parametrize("port,label", INTERNAL_PORTS)
def test_7_internal_port_closed(target_host, record, port, label):
    open_ = _tcp_open(target_host, port)
    severity = "Critical" if port == 2019 else "High"
    record(
        Finding(
            id=f"7.{port}",
            title=f"Port {port} ({label}) must not be reachable from the internet",
            severity=severity,
            status="vulnerable" if open_ else "verified",
            summary=f"TCP connect to {target_host}:{port} from the auditor's network.",
            details={"port": port, "label": label, "open": open_},
        ),
    )
    assert not open_, f"{label} ({port}) reachable externally"


def test_7_2_caddy_admin_http(target_host, record):
    open_ = _tcp_open(target_host, 2019)
    if not open_:
        record(
            Finding(
                id="7.2",
                title="Caddy admin /config/ unreachable",
                severity="Informational",
                status="informational",
                summary="Port 2019 closed; admin surface not exposed.",
                details={"port": 2019, "open": False},
            ),
        )
        return
    with httpx.Client(timeout=5.0) as c:
        r = c.get(f"http://{target_host}:2019/config/")
    leaked = r.status_code == 200 and "apps" in r.text
    record(
        Finding(
            id="7.2",
            title="Caddy admin /config/ reachable",
            severity="Critical",
            status="vulnerable" if leaked else "informational",
            summary=(
                "Port 2019 open and /config/ responding — full Caddy reconfig surface exposed."
            ),
            details={"status_code": r.status_code, "body_excerpt": r.text[:200]},
        ),
    )
    assert not leaked, "Caddy admin surface exposed"


def test_7_4_chisel_port_documented(target_host, record):
    open_ = _tcp_open(target_host, 7000)
    record(
        Finding(
            id="7.4",
            title="Chisel server port 7000",
            severity="Informational",
            status="informational",
            summary="Chisel port is intentionally public for SerialHop reverse tunnels.",
            details={"port": 7000, "open": open_},
        ),
    )
