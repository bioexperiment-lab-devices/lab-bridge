from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from itsdangerous import BadSignature, URLSafeSerializer

from app.config import Settings
from app.paths import safe_join, sanitize_filename
from app.templates import templates

ALLOWED_DOC_EXT = {".md", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
MAX_DOC_BYTES = 10 * 1024 * 1024


def _serializer(secret: str) -> URLSafeSerializer:
    return URLSafeSerializer(secret, salt="csrf")


def _make_csrf(serializer: URLSafeSerializer) -> str:
    return serializer.dumps("ok")


def _check_csrf(serializer: URLSafeSerializer, token: str | None) -> None:
    if not token:
        raise HTTPException(status_code=403, detail="missing csrf")
    try:
        serializer.loads(token)
    except BadSignature as e:
        raise HTTPException(status_code=403, detail="bad csrf") from e


def _resolve_target(docs_root: Path, target: str) -> Path:
    parts = [p for p in target.split("/") if p]
    if not parts:
        return docs_root.resolve()
    try:
        clean = [sanitize_filename(p) for p in parts]
    except ValueError as e:
        raise HTTPException(status_code=400, detail="bad target") from e
    # Navigation paths must be canonical: any segment that would be rewritten
    # by sanitisation (e.g. "<script>" -> "-script-") is rejected outright so
    # we never silently create dirs from messy/attacker-controlled input.
    if clean != parts:
        raise HTTPException(status_code=400, detail="bad target")
    try:
        return safe_join(docs_root, *clean)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="bad target") from e


def _list_dir(path: Path) -> list[dict[str, object]]:
    if not path.is_dir():
        return []
    out: list[dict[str, object]] = []
    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name.startswith("."):
            continue
        st = child.stat()
        out.append(
            {
                "name": child.name,
                "is_dir": child.is_dir(),
                "size": st.st_size,
                "mtime": st.st_mtime,
            }
        )
    return out


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/admin")
    serializer = _serializer(settings.csrf_secret)

    @router.get("/", include_in_schema=False)
    @router.get("", include_in_schema=False)
    def dashboard(request: Request) -> Response:
        from app.agent import load_meta

        info = load_meta(settings.agent_root)
        docs_count = sum(1 for _ in settings.docs_root.rglob("*.md"))
        last_doc = None
        if docs_count:
            last_doc = max(
                (p.stat().st_mtime for p in settings.docs_root.rglob("*.md")),
                default=0,
            )
        return templates.TemplateResponse(
            request,
            "admin/index.html",
            {
                "docs_count": docs_count,
                "last_doc_mtime": last_doc,
                "agent_info": info,
            },
        )

    @router.get("/docs", include_in_schema=False)
    def docs_manager(request: Request, target: str = "") -> Response:
        target_path = _resolve_target(settings.docs_root, target)
        return templates.TemplateResponse(
            request,
            "admin/docs.html",
            {
                "target": target,
                "items": _list_dir(target_path),
                "csrf": _make_csrf(serializer),
            },
        )

    @router.post("/docs/upload")
    async def upload(
        target: str = Form(""),
        csrf: str = Form(""),
        files: list[UploadFile] = File(...),
    ) -> Response:
        _check_csrf(serializer, csrf)
        target_path = _resolve_target(settings.docs_root, target)
        target_path.mkdir(parents=True, exist_ok=True)
        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail="target is not a directory")
        for upload in files:
            name = sanitize_filename(upload.filename or "")
            ext = Path(name).suffix.lower()
            if ext not in ALLOWED_DOC_EXT:
                raise HTTPException(status_code=400, detail=f"disallowed extension: {ext}")
            dest = safe_join(target_path, name)
            written = 0
            with dest.open("wb") as out:
                while True:
                    chunk = await upload.read(64 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_DOC_BYTES:
                        out.close()
                        dest.unlink(missing_ok=True)
                        raise HTTPException(status_code=413, detail="file too large")
                    out.write(chunk)
        return RedirectResponse(url=f"/admin/docs?target={target}", status_code=303)

    @router.post("/docs/delete")
    def delete(target: str = Form(""), csrf: str = Form(""), name: str = Form(...)) -> Response:
        _check_csrf(serializer, csrf)
        target_path = _resolve_target(settings.docs_root, target)
        clean = sanitize_filename(name)
        victim = safe_join(target_path, clean)
        if victim.is_dir():
            try:
                victim.rmdir()
            except OSError as e:
                raise HTTPException(status_code=400, detail="directory not empty") from e
        elif victim.is_file():
            victim.unlink()
        else:
            raise HTTPException(status_code=404)
        return RedirectResponse(url=f"/admin/docs?target={target}", status_code=303)

    @router.post("/docs/rename")
    def rename(
        target: str = Form(""),
        csrf: str = Form(""),
        old: str = Form(...),
        new: str = Form(...),
    ) -> Response:
        _check_csrf(serializer, csrf)
        target_path = _resolve_target(settings.docs_root, target)
        old_clean = sanitize_filename(old)
        new_clean = sanitize_filename(new)
        src = safe_join(target_path, old_clean)
        dst = safe_join(target_path, new_clean)
        if not src.exists():
            raise HTTPException(status_code=404)
        if dst.exists():
            raise HTTPException(status_code=409, detail="destination exists")
        src.rename(dst)
        return RedirectResponse(url=f"/admin/docs?target={target}", status_code=303)

    @router.post("/docs/new-folder")
    def new_folder(
        target: str = Form(""), csrf: str = Form(""), name: str = Form(...)
    ) -> Response:
        _check_csrf(serializer, csrf)
        target_path = _resolve_target(settings.docs_root, target)
        clean = sanitize_filename(name)
        new_dir = safe_join(target_path, clean)
        try:
            new_dir.mkdir(parents=False, exist_ok=False)
        except FileExistsError as e:
            raise HTTPException(status_code=409, detail="exists") from e
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail="parent missing") from e
        return RedirectResponse(url=f"/admin/docs?target={target}", status_code=303)

    return router
