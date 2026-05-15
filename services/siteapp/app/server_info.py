from __future__ import annotations

from fastapi import APIRouter

from app.config import Settings

# Forward-tunnel topology is pinned by the compose stack today:
# - chisel-users.json grants every client `loki:3100` as a forward target
#   (see compose/chisel-users.json.tmpl and scripts/lib/render.sh:41).
# - The agent opens a `-L 127.0.0.1:3100:loki:3100` tunnel and POSTs to
#   the local end of it.
# If you change EITHER the chisel allow-list OR the loki service name/port,
# update these constants in lockstep. Promote to config.yaml when a second
# forward target appears.
LOKI_PUSH_URL = "http://127.0.0.1:3100/loki/api/v1/push"
FORWARD_TUNNELS: list[dict[str, str]] = [
    {"name": "loki", "local": "127.0.0.1:3100", "remote": "loki:3100"},
]


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/api/public/server-info")
    def get_server_info() -> dict:
        return {
            "chisel": {"listen_port": settings.chisel_listen_port},
            "loki": {"push_url": LOKI_PUSH_URL},
            "forward_tunnels": FORWARD_TUNNELS,
            "version": settings.version,
            "git_sha": settings.git_sha,
        }

    return router
