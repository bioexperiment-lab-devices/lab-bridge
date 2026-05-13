from __future__ import annotations

import pytest

from app.flash import JobStore, run_flash_job
from app.serialhop import UpstreamErrorResponse, UpstreamUnreachable


def test_job_store_starts_empty() -> None:
    store = JobStore(capacity=3)
    assert store.current() is None


def test_create_returns_unique_ids() -> None:
    store = JobStore(capacity=3)
    a = store.create(client="x", port="COM3", firmware_sha256="aa", firmware_size=10)
    b = store.create(client="x", port="COM3", firmware_sha256="aa", firmware_size=10)
    assert a != b


def test_current_returns_most_recent_running() -> None:
    store = JobStore(capacity=3)
    store.create(client="x", port="COM3", firmware_sha256="aa", firmware_size=10)
    latest = store.create(client="x", port="COM4", firmware_sha256="bb", firmware_size=10)
    current = store.current()
    assert current is not None
    assert current["job_id"] == latest
    assert current["status"] == "running"


def test_complete_marks_done_with_result() -> None:
    store = JobStore(capacity=3)
    job_id = store.create(client="x", port="COM3", firmware_sha256="aa", firmware_size=10)
    store.complete(job_id, result={"outcome": "success"})
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "done"
    assert record["result"] == {"outcome": "success"}


def test_fail_marks_error_with_code_and_detail() -> None:
    store = JobStore(capacity=3)
    job_id = store.create(client="x", port="COM3", firmware_sha256="aa", firmware_size=10)
    store.fail(job_id, error_code="upstream unreachable", detail="connection refused")
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "error"
    assert record["error_code"] == "upstream unreachable"
    assert record["detail"] == "connection refused"


def test_capacity_prunes_oldest_first() -> None:
    store = JobStore(capacity=2)
    a = store.create(client="x", port="COM3", firmware_sha256="aa", firmware_size=10)
    b = store.create(client="x", port="COM4", firmware_sha256="bb", firmware_size=10)
    c = store.create(client="x", port="COM5", firmware_sha256="cc", firmware_size=10)
    assert store.get(a) is None
    assert store.get(b) is not None
    assert store.get(c) is not None


def test_get_unknown_returns_none() -> None:
    store = JobStore(capacity=3)
    assert store.get("nope") is None


class _FakeClient:
    def __init__(self, *, disconnect_result=None, flash_result=None, raise_on_flash=None) -> None:
        self.disconnect_result = disconnect_result or {"released": 0}
        self.flash_result = flash_result
        self.raise_on_flash = raise_on_flash
        self.calls: list[tuple[str, dict]] = []

    async def disconnect_devices(self) -> dict:
        self.calls.append(("disconnect", {}))
        return self.disconnect_result

    async def flash(self, **kwargs) -> dict:
        self.calls.append(("flash", kwargs))
        if self.raise_on_flash is not None:
            raise self.raise_on_flash
        assert self.flash_result is not None
        return self.flash_result


@pytest.mark.asyncio
async def test_run_flash_job_success() -> None:
    store = JobStore(capacity=3)
    job_id = store.create(client="x", port="COM3", firmware_sha256="aa", firmware_size=10)
    fake = _FakeClient(flash_result={"outcome": "success", "port": "COM3", "stages": {}})

    await run_flash_job(
        store=store,
        job_id=job_id,
        client=fake,
        port="COM3",
        firmware=":00000001FF\n",
        test_command=None,
        expected_response=None,
    )

    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "done"
    assert record["result"]["outcome"] == "success"
    assert [c[0] for c in fake.calls] == ["disconnect", "flash"]


@pytest.mark.asyncio
async def test_run_flash_job_passes_test_pair_when_provided() -> None:
    store = JobStore(capacity=3)
    job_id = store.create(client="x", port="COM3", firmware_sha256="aa", firmware_size=10)
    fake = _FakeClient(flash_result={"outcome": "success", "port": "COM3", "stages": {}})

    await run_flash_job(
        store=store,
        job_id=job_id,
        client=fake,
        port="COM3",
        firmware=":00000001FF\n",
        test_command="010203",
        expected_response="aabbcc",
    )

    flash_kwargs = next(c for c in fake.calls if c[0] == "flash")[1]
    assert flash_kwargs["test_command"] == "010203"
    assert flash_kwargs["expected_response"] == "aabbcc"


@pytest.mark.asyncio
async def test_run_flash_job_marks_error_on_upstream_unreachable() -> None:
    store = JobStore(capacity=3)
    job_id = store.create(client="x", port="COM3", firmware_sha256="aa", firmware_size=10)
    fake = _FakeClient(raise_on_flash=UpstreamUnreachable(detail="connection refused"))

    await run_flash_job(
        store=store,
        job_id=job_id,
        client=fake,
        port="COM3",
        firmware=":00000001FF\n",
        test_command=None,
        expected_response=None,
    )

    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "error"
    assert record["error_code"] == "upstream unreachable"
    assert "connection refused" in record["detail"]


@pytest.mark.asyncio
async def test_run_flash_job_propagates_serialhop_error_envelope() -> None:
    store = JobStore(capacity=3)
    job_id = store.create(client="x", port="COM3", firmware_sha256="aa", firmware_size=10)
    fake = _FakeClient(
        raise_on_flash=UpstreamErrorResponse(
            status_code=409, error_code="flash in flight", detail="busy"
        )
    )

    await run_flash_job(
        store=store,
        job_id=job_id,
        client=fake,
        port="COM3",
        firmware=":00000001FF\n",
        test_command=None,
        expected_response=None,
    )

    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "error"
    assert record["error_code"] == "flash in flight"
    assert record["detail"] == "busy"
