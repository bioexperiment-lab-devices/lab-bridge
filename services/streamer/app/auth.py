"""Identity extraction from Caddy/Authelia forward_auth Remote-* headers."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException


_ALLOWED_GROUPS = {"researchers", "admins"}


@dataclass(frozen=True)
class Identity:
    user: str
    groups: list[str]


def get_remote_identity(
    remote_user: str | None = Header(default=None, alias="Remote-User"),
    remote_groups: str | None = Header(default=None, alias="Remote-Groups"),
) -> Identity:
    if not remote_user:
        raise HTTPException(status_code=401, detail="unauthenticated")
    groups = [g.strip() for g in (remote_groups or "").split(",") if g.strip()]
    if not (_ALLOWED_GROUPS & set(groups)):
        raise HTTPException(status_code=403, detail="forbidden")
    return Identity(user=remote_user, groups=groups)


RequiredGroupsDep = Depends(get_remote_identity)
