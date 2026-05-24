"""One-shot WHIP bearer tokens.

A token is generated server-side when a Session is created, sent to
SerialHop in the start command, and validated on the WHIP POST. After
first successful match the token is *burned* (cannot match again).
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass


_TOKEN_PREFIX = "tk_"


@dataclass
class WhipToken:
    value: str
    created_at: float
    validity_s: float
    _burned: bool = False

    def matches(self, candidate: str) -> bool:
        if self._burned:
            return False
        if time.monotonic() - self.created_at > self.validity_s:
            return False
        return secrets.compare_digest(self.value, candidate)

    def burn(self) -> None:
        self._burned = True

    @property
    def is_burned(self) -> bool:
        return self._burned


def generate_whip_token(*, validity_s: float) -> WhipToken:
    raw = secrets.token_urlsafe(32)
    return WhipToken(
        value=f"{_TOKEN_PREFIX}{raw}",
        created_at=time.monotonic(),
        validity_s=validity_s,
    )
