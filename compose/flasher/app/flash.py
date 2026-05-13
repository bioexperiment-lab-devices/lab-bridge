from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from typing import Any, Literal, Protocol

from app.serialhop import (
    SerialHopError,
    UpstreamErrorResponse,
    UpstreamUnreachable,
)

JobStatus = Literal["running", "done", "error"]


class _SerialHopLike(Protocol):
    async def disconnect_devices(self) -> dict: ...
    async def flash(self, **kwargs: Any) -> dict: ...


class JobStore:
    """Bounded in-memory job registry.

    Keeps the N most recent jobs; older entries are pruned on insert.
    Insertion order is preserved so .current() returns the most recent.
    """

    def __init__(self, capacity: int = 10) -> None:
        self._capacity = capacity
        self._jobs: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def create(
        self,
        *,
        client: str,
        port: str,
        firmware_sha256: str,
        firmware_size: int,
    ) -> str:
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "client": client,
            "port": port,
            "firmware_sha256": firmware_sha256,
            "firmware_size": firmware_size,
            "started_at_monotonic": time.monotonic(),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        while len(self._jobs) > self._capacity:
            self._jobs.popitem(last=False)
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        record = self._jobs.get(job_id)
        if record is None:
            return None
        return self._snapshot(record)

    def current(self) -> dict[str, Any] | None:
        if not self._jobs:
            return None
        last_id = next(reversed(self._jobs))
        return self._snapshot(self._jobs[last_id])

    def complete(self, job_id: str, *, result: dict) -> None:
        self._jobs[job_id]["status"] = "done"
        self._jobs[job_id]["result"] = result

    def fail(self, job_id: str, *, error_code: str, detail: str) -> None:
        self._jobs[job_id]["status"] = "error"
        self._jobs[job_id]["error_code"] = error_code
        self._jobs[job_id]["detail"] = detail

    def _snapshot(self, record: dict[str, Any]) -> dict[str, Any]:
        out = {
            "job_id": record["job_id"],
            "status": record["status"],
            "client": record["client"],
            "port": record["port"],
            "started_at": record["started_at"],
        }
        if record["status"] == "running":
            elapsed = time.monotonic() - record["started_at_monotonic"]
            out["elapsed_ms"] = int(elapsed * 1000)
        if record["status"] == "done":
            out["result"] = record["result"]
        if record["status"] == "error":
            out["error_code"] = record["error_code"]
            out["detail"] = record["detail"]
        return out


async def run_flash_job(
    *,
    store: JobStore,
    job_id: str,
    client: _SerialHopLike,
    port: str,
    firmware: str,
    test_command: str | None,
    expected_response: str | None,
    skip_backup: bool = False,
) -> None:
    """Run the disconnect -> flash sequence and write the outcome into the store.

    Never raises. Any exception is converted to a job-level error record so
    the polling endpoint can surface it.
    """
    try:
        await client.disconnect_devices()
        kwargs: dict[str, Any] = {"port": port, "firmware": firmware}
        if test_command is not None and expected_response is not None:
            kwargs["test_command"] = test_command
            kwargs["expected_response"] = expected_response
        if skip_backup:
            kwargs["skip_backup"] = True
        result = await client.flash(**kwargs)
        store.complete(job_id, result=result)
    except UpstreamErrorResponse as exc:
        store.fail(job_id, error_code=exc.error_code, detail=exc.detail)
    except UpstreamUnreachable as exc:
        store.fail(job_id, error_code="upstream unreachable", detail=exc.detail)
    except SerialHopError as exc:  # safety net
        store.fail(job_id, error_code="upstream error", detail=str(exc))
