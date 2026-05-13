from __future__ import annotations

from dataclasses import dataclass

import httpx

# Flash on a 32 KB AVR has a worst-case wall time of ~36 s; an indeterminate
# rollback path can push slightly higher. The HTTP read timeout is generous
# so a slow board never appears as an "upstream unreachable" to the user.
FLASH_REQUEST_TIMEOUT_S = 120.0
SHORT_REQUEST_TIMEOUT_S = 5.0


class SerialHopError(Exception):
    """Base class for all SerialHop transport-level failures."""


@dataclass
class UpstreamUnreachable(SerialHopError):
    """SerialHop could not be reached at all (DNS, connect, read timeout)."""

    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass
class UpstreamErrorResponse(SerialHopError):
    """SerialHop returned a non-200 response.

    For SerialHop's standard 4xx error envelope (`{error, detail}`), the
    fields are surfaced verbatim. For any other non-200, error_code is
    `"upstream error"` and detail is the raw status + body excerpt.
    """

    status_code: int
    error_code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.error_code}: {self.detail}"


class SerialHopClient:
    """Thin async wrapper over one SerialHop instance.

    Builds URLs as http://<host>:<port>/... and raises a SerialHopError
    subclass on any non-200 outcome. Successful 200s are returned as
    parsed JSON (the body shapes are defined by docs/flashing-server-brief.md).
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = f"http://{host}:{port}"
        self._transport = transport

    def _client(self, *, timeout_s: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout_s,
            transport=self._transport,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        timeout_s: float = SHORT_REQUEST_TIMEOUT_S,
    ) -> dict:
        try:
            async with self._client(timeout_s=timeout_s) as client:
                response = await client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise UpstreamUnreachable(detail=str(exc) or type(exc).__name__) from exc

        if response.status_code == 200:
            return response.json()

        # Try SerialHop's standard envelope first.
        try:
            body = response.json()
            error_code = body.get("error") if isinstance(body, dict) else None
            detail = body.get("detail", "") if isinstance(body, dict) else ""
        except ValueError:
            error_code = None
            detail = ""

        if error_code:
            raise UpstreamErrorResponse(
                status_code=response.status_code,
                error_code=str(error_code),
                detail=str(detail),
            )

        # Any other non-200: fall through to a generic "upstream error".
        body_excerpt = response.text[:200] if response.text else ""
        raise UpstreamErrorResponse(
            status_code=response.status_code,
            error_code="upstream error",
            detail=f"HTTP {response.status_code}: {body_excerpt}",
        )

    async def get_ports_detailed(self) -> dict:
        return await self._request("GET", "/serial/ports/detailed")

    async def disconnect_devices(self) -> dict:
        return await self._request("POST", "/devices/disconnect")

    async def flash(
        self,
        *,
        port: str,
        firmware: str,
        test_command: str | None = None,
        expected_response: str | None = None,
    ) -> dict:
        if (test_command is None) != (expected_response is None):
            raise ValueError("test_command and expected_response must both be set or both omitted")
        body: dict[str, object] = {"firmware": firmware}
        if test_command is not None:
            body["test_command"] = test_command
            body["expected_response"] = expected_response
        return await self._request(
            "POST",
            f"/flash/{port}",
            json=body,
            timeout_s=FLASH_REQUEST_TIMEOUT_S,
        )
