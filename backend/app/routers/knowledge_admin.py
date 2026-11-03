"""Back office: the knowledge database (MEDORA_KNOWLEDGE_DATABASE_URL).

What it holds (counted live) and uploading files into it. There is no
browsing of raw passages on purpose (2026-11-02: meaningless to operators). The
app database (Supabase) holds no medical knowledge any more: everything here
reads and writes the knowledge database only.
"""

import asyncio
import uuid
from pathlib import Path

from anyio import to_thread
from fastapi import APIRouter, HTTPException, Request, UploadFile

from ..deps import Admin, AppSettings
from ..kb.uploads import PDF_KINDS, TIERS, UploadDesk, UploadError
from ..schemas import ApiModel
from ..tenancy import record

router = APIRouter(prefix="/api/admin/knowledge", dependencies=[Admin])

_CHUNK = 1024 * 1024


def _desk(request: Request) -> UploadDesk:
    desk = request.app.state.uploads
    try:
        desk.loop = asyncio.get_running_loop()
    except RuntimeError:  # called from a worker thread
        pass
    return desk


def _fail(error: UploadError):
    raise HTTPException(error.status, str(error)) from error


def _upload_out(u: dict, detail: bool = False) -> dict:
    stats, plan, meta = u["stats"] or {}, u["plan"] or {}, u["meta"] or {}
    out = {
        "id": u["id"],
        "filename": u["filename"],
        "sizeBytes": u["bytes"],
        "kind": u["kind"],
        "status": u["status"],
        "stage": u["stage"],
        "note": u["note"],
        "title": meta.get("title", ""),
        "publisher": meta.get("publisher", ""),
        "tier": meta.get("tier", 5),
        "reports": meta.get("production_allowed", False),
        "createdAt": u["created_at"].isoformat(),
        "updatedAt": u["updated_at"].isoformat(),
        "summary": plan.get("summary", ""),
        "verdict": plan.get("verdict", ""),
        "needsReview": stats.get("needs_review", []),
        "preview": stats.get("preview"),
        "loaded": stats.get("loaded"),
    }
    if detail:
        out |= {
            "reason": plan.get("reason", ""),
            "model": plan.get("model", ""),
            "confidence": plan.get("confidence", 0),
            "content": plan.get("content", ""),
            "outputs": plan.get("outputs", []) if plan.get("content") != "article" else [],
            "revised": stats.get("revised", []),
            "droppedNotInArticle": stats.get("dropped_not_in_article", []),
            "licence": meta.get("licence", ""),
            "documentKind": meta.get("kind", ""),
        }
    return out


# --- what is in it ----------------------------------------------------------


@router.get("/summary")
async def summary(request: Request, settings: AppSettings) -> dict:
    """Counts from the knowledge database (reused for a few seconds; the last
    counts when it cannot be reached), plus how the reports' searches stand."""
    out = await to_thread.run_sync(request.app.state.kb_stats.summary)
    kb = request.app.state.kb
    out["evidenceIndex"] = {"available": kb.available(), "from": kb.source}
    out["switches"] = {"testing": settings.knowledge_testing_sources, "community": settings.knowledge_community_sources}
    out["choices"] = {"tiers": {str(k): v for k, v in TIERS.items()}, "documentKinds": PDF_KINDS}
    return out


# --- uploads ----------------------------------------------------------------


@router.get("/uploads")
async def list_uploads(request: Request) -> list[dict]:
    try:
        uploads = await to_thread.run_sync(_desk(request).list)
    except UploadError as e:
        _fail(e)
    return [_upload_out(u) for u in uploads]


@router.get("/uploads/{upload_id}")
async def upload_detail(upload_id: int, request: Request) -> dict:
    try:
        upload = await to_thread.run_sync(_desk(request).get, upload_id)
    except UploadError as e:
        _fail(e)
    return _upload_out(upload, detail=True)


@router.post("/uploads", status_code=201)
async def upload(
    file: UploadFile,
    request: Request,
    settings: AppSettings,
    title: str = "",
    publisher: str = "",
    edition: str = "",
    licence: str = "",
    tier: int = 5,
    kind: str = "guideline",
    reports: bool = False,
) -> dict:
    """Stores a file and starts on it: a PDF is read and loaded at once; a
    data file or article is planned by the AI and waits for approval."""
    desk = _desk(request)
    if not desk.configured:
        raise HTTPException(503, "The knowledge database is not set up (MEDORA_KNOWLEDGE_DATABASE_URL)")
    # The uploaded name is only displayed; on disk the file gets a generated
    # name, so path tricks in it cannot escape the uploads folder.
    original = Path(file.filename or "").name
    if not original:
        raise HTTPException(400, "The file has no name")
    desk.folder.mkdir(parents=True, exist_ok=True)
    target = desk.folder / (uuid.uuid4().hex + Path(original).suffix.lower()[:16])
    limit = settings.max_upload_mb * 1024 * 1024
    size = 0
    user = getattr(getattr(request.state, "admin_user", None), "email", "") or ""
    try:
        with target.open("wb") as out:
            while chunk := await file.read(_CHUNK):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "The file is empty")
        meta = {"title": title, "publisher": publisher, "edition": edition, "licence": licence,
                "tier": tier, "kind": kind, "reports": reports}
        created = await to_thread.run_sync(desk.receive, target, original[:255], meta, user)
    except UploadError as e:
        target.unlink(missing_ok=True)
        _fail(e)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    record(request.app.state.engine, "knowledge.uploaded", f"{original} ({created['kind']})")
    return _upload_out(created)


class ReasonBody(ApiModel):
    text: str


@router.post("/uploads/{upload_id}/{action}")
async def act(upload_id: int, action: str, request: Request, body: ReasonBody | None = None) -> dict:
    """approve | reject | revise | retry | remove | allow | block (reports' use)."""
    desk = _desk(request)
    text = (body.text if body else "").strip()
    try:
        if action == "approve":
            upload = await to_thread.run_sync(desk.approve, upload_id)
        elif action == "reject":
            if not text:
                raise HTTPException(422, "Say why the file is rejected")
            upload = await to_thread.run_sync(desk.reject, upload_id, text)
        elif action == "revise":
            if not text:
                raise HTTPException(422, "Say what should change")
            upload = await desk.revise(upload_id, text)
        elif action == "retry":
            upload = await to_thread.run_sync(desk.retry, upload_id)
        elif action == "remove":
            upload = await to_thread.run_sync(desk.remove, upload_id)
        elif action in ("allow", "block"):
            upload = await to_thread.run_sync(desk.set_reports, upload_id, action == "allow")
        else:
            raise HTTPException(404, "Unknown action")
    except UploadError as e:
        _fail(e)
    record(request.app.state.engine, f"knowledge.{action}", f"{upload['filename']}: {upload['status']}",
           level="error" if upload["status"] == "failed" else "info")
    return _upload_out(upload)
