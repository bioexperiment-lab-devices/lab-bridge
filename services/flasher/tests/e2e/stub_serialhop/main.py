"""Tiny FastAPI app that pretends to be SerialHop for flasher e2e tests.

Behavior is controlled via env vars set on the compose service:
- STUB_FLASH_OUTCOME: one of "success", "rolled_back_test_failed",
  "rolled_back_verify_failed", "failed_backup", "failed_preflight",
  "failed_no_recovery". Default "success".
- STUB_PORTS_JSON: JSON for GET /serial/ports/detailed response.
  Default returns one Arduino-shaped port.
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI

app = FastAPI()


DEFAULT_PORTS = {
    "ports": [
        {
            "name": "COM3",
            "is_usb": True,
            "vid": "2341",
            "pid": "0043",
            "serial_number": "TEST-SERIAL",
            "product": "Arduino Uno (stub)",
            "discovered": False,
            "device_id": "",
        }
    ]
}


def _flash_response(port: str, outcome: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "outcome": outcome,
        "port": port,
        "stages": {
            "preflight": {"status": "ok", "duration_ms": 12},
            "backup": {"status": "ok", "duration_ms": 100},
            "erase": {"status": "ok", "duration_ms": 50},
            "program": {"status": "ok", "duration_ms": 200},
            "verify": {"status": "ok", "duration_ms": 100},
            "test": {"status": "n/a"},
            "rollback": {"status": "n/a"},
        },
        "backup": {
            "hex": ":00000001FF\n",
            "saved_path": "/tmp/stub.hex",
            "sha256": "0" * 64,
            "size_bytes": 12,
            "scope": "flash_only",
        },
    }
    if outcome == "rolled_back_test_failed":
        base["stages"]["test"] = {"status": "failed", "duration_ms": 50, "error": "mismatch"}
        base["stages"]["rollback"] = {"status": "ok", "duration_ms": 200, "verify_status": "ok"}
        base["test_result"] = {"sent": "010203", "expected": "aabbcc", "received": "0000", "match": False}
    elif outcome == "rolled_back_verify_failed":
        base["stages"]["verify"] = {"status": "failed", "duration_ms": 100, "first_mismatch_offset": "0x010"}
        base["stages"]["rollback"] = {"status": "ok", "duration_ms": 200, "verify_status": "ok"}
    elif outcome == "failed_backup":
        base["stages"]["backup"] = {"status": "failed", "duration_ms": 50, "error": "no device"}
        base["stages"]["erase"] = {"status": "skipped"}
        base["stages"]["program"] = {"status": "skipped"}
        base["stages"]["verify"] = {"status": "skipped"}
        base["backup"] = None
    elif outcome == "failed_no_recovery":
        base["stages"]["verify"] = {"status": "failed", "duration_ms": 100}
        base["stages"]["rollback"] = {"status": "failed", "duration_ms": 200, "verify_status": "failed"}
        base["recovery_hint"] = "use an ISP programmer; backup preserved with -LOCKED- marker"
    elif outcome == "success":
        # success: include test=ok with positive result
        base["stages"]["test"] = {"status": "ok", "duration_ms": 50}
        base["test_result"] = {"sent": "010203", "expected": "aabbcc", "received": "aabbcc", "match": True}
    return base


@app.get("/serial/ports/detailed")
def get_ports() -> dict:
    raw = os.environ.get("STUB_PORTS_JSON")
    if raw:
        return json.loads(raw)
    return DEFAULT_PORTS


@app.post("/devices/disconnect")
def disconnect() -> dict:
    return {"released": 0}


@app.post("/flash/{port}")
def flash(port: str) -> dict:
    outcome = os.environ.get("STUB_FLASH_OUTCOME", "success")
    return _flash_response(port, outcome)
