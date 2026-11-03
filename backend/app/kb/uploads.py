"""Files uploaded in the back office (Database tab) into the knowledge database.

Every upload becomes a source of its own, loaded exactly like a source
registered in sources.py and loaded with `python -m app.kb load`: the same
readers, checks, quarantine, linking, embedding and offline snapshot. Nothing
goes to the app database (Supabase); the history lives in `kb_uploads`.

  PDF (guideline, drug book, patient information)
      the `guideline` reader (text layer; picture pages through Gemini vision
      with the number check) -> load -> link -> embed -> offline snapshot.
      Starts at once: whoever uploads states the publisher and licence.
  Data file (CSV, TSV, JSON, OBO/OWL, XML, Excel)
      the AI plans how its columns map (app/ingest), code applies the plan;
      the plan and a preview wait for approval, because the planner has been
      wrong before (package sizes mapped to doses). Approve -> load -> link.
  Article (plain text about one disease)
      the AI extracts its facts, every name checked against the text; waits
      for approval like a data file.

One file is worked on at a time; the others wait. A server restart marks a
file that was in the middle of a step as interrupted (Retry picks it up).
"""

import asyncio
import csv
import hashlib
import logging
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from ..ingest import records
from ..ingest.articles import ARTICLE_PLAN, extract_article
from ..ingest.plan import Plan
from ..ingest.planner import make_plan
from ..ingest.sniff import sniff
from ..ingest.transform import apply_plan
from ..llm import Llm, LlmError
from . import load as loader
from .sources import Source
from .staged import bundle_from_staged

log = logging.getLogger("medora.kb.uploads")

PREVIEW_RECORDS = 5000
# A load is refused when more than this share of values fails validation:
# the mapping is probably wrong.
MAX_REJECT_RATE = 0.4
REVIEW_BELOW_CONFIDENCE = 0.8
FLOOD_THRESHOLD = 2000

TIERS = {1: "Indian government", 2: "WHO or international body", 3: "Other reference", 5: "Community dataset"}
PDF_KINDS = {"guideline": "Clinical guideline", "formulary": "Drug book (formulary)", "patient_info": "Patient information"}
RECORD_FORMATS = ("csv", "json", "obo", "owl", "xml")
BUSY = ("waiting", "reading", "loading")


class UploadError(Exception):
    """A request the desk refuses; the message is for the person uploading."""

    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def kind_of(path: Path) -> tuple[str, str]:
    """(kind, format): pdf, records (csv/json/obo/owl/xml; Excel is turned
    into CSV first), article (prose) or other (not something to load)."""
    with path.open("rb") as f:
        head = f.read(8)
    if head.startswith(b"%PDF"):
        return "pdf", "pdf"
    if head.startswith(b"PK") and path.suffix.lower() in (".xlsx", ".xlsm"):
        return "records", "xlsx"
    sniffed = sniff(path)
    if sniffed.format in RECORD_FORMATS:
        return "records", sniffed.format
    if sniffed.format == "text":
        return "article", "text"
    return "other", sniffed.format


def excel_to_csv(path: Path) -> Path:
    """The first sheet with data, as CSV beside the file."""
    from openpyxl import load_workbook

    target = path.with_suffix(".csv")
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = next((s for s in book.worksheets if (s.max_row or 0) > 1), book.worksheets[0])
        with target.open("w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out)
            for row in sheet.iter_rows(values_only=True):
                if any(v not in (None, "") for v in row):
                    writer.writerow(["" if v is None else str(v) for v in row])
    finally:
        book.close()
    return target


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:32] or "file"


def clean_meta(meta: dict, kind: str, filename: str) -> dict:
    """What the uploader said about the file, checked."""
    title = (meta.get("title") or "").strip() or Path(filename).stem.replace("_", " ")
    try:
        tier = int(meta.get("tier") or 5)
    except ValueError as e:
        raise UploadError("Choose who publishes the file", 422) from e
    if tier not in TIERS:
        raise UploadError("Choose who publishes the file", 422)
    pdf_kind = meta.get("kind") or "guideline"
    if kind == "pdf" and pdf_kind not in PDF_KINDS:
        raise UploadError("Choose what kind of document it is", 422)
    return {
        "title": title[:200],
        "publisher": (meta.get("publisher") or "").strip()[:200] or "Not stated",
        "edition": (meta.get("edition") or "").strip()[:80],
        "licence": (meta.get("licence") or "").strip()[:300] or "Not stated",
        "tier": tier,
        "kind": pdf_kind if kind == "pdf" else "data" if kind == "records" else "article",
        "production_allowed": str(meta.get("reports", "")).lower() in ("1", "true", "yes", "on"),
    }


def source_for(upload: dict) -> Source:
    meta = upload["meta"]
    reader = "guideline" if upload["kind"] == "pdf" else "upload"
    return Source(
        upload["source_key"], meta["title"], meta["publisher"], meta.get("edition", ""), meta["kind"], meta["tier"],
        meta["licence"], meta["production_allowed"], (upload["path"],), reader,
        f"Uploaded in the back office as {upload['filename']!r}" + (f" by {upload['created_by']}" if upload.get("created_by") else ""),
    )


_COLUMNS = ("id", "filename", "sha256", "bytes", "path", "kind", "status", "stage", "source_key", "meta", "plan",
            "stats", "note", "created_by", "created_at", "updated_at")


class UploadDesk:
    def __init__(self, url: str, llm: Llm, folder: Path, settings=None, retriever=None,
                 on_loaded: Callable[[], None] | None = None):
        self.url = url
        self.llm = llm
        self.folder = folder
        self.settings = settings
        self.retriever = retriever
        self.on_loaded = on_loaded
        self._queue: asyncio.Lock | None = None
        self._tasks: set[asyncio.Task] = set()
        # The server's event loop: steps are started from worker threads.
        self.loop: asyncio.AbstractEventLoop | None = None
        self._ready = False
        self._ready_lock = threading.Lock()

    # --- database ---------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self.url)

    def connect(self) -> psycopg.Connection:
        if not self.url:
            raise UploadError("The knowledge database is not set up (MEDORA_KNOWLEDGE_DATABASE_URL)", 503)
        try:
            conn = psycopg.connect(self.url.replace("postgresql+psycopg://", "postgresql://"), connect_timeout=8,
                                   prepare_threshold=None, keepalives=1, keepalives_idle=20,
                                   keepalives_interval=10, keepalives_count=3)
        except psycopg.OperationalError as e:
            raise UploadError("The knowledge database cannot be reached right now. Try again when it is on.", 503) from e
        self._prepare(conn)
        return conn

    def _prepare(self, conn: psycopg.Connection) -> None:
        """Creates the tables once per run (safe to repeat), and marks files
        a restart interrupted."""
        if self._ready:
            return
        with self._ready_lock:
            if self._ready:
                return
            try:
                loader.init_schema(conn)
            except SystemExit as e:  # missing extension: the message says what to run
                raise UploadError(str(e), 503) from e
            conn.execute(
                """update kb_uploads set status='failed', stage='', updated_at=now(),
                   note='Interrupted by a server restart. Press Retry to start it again.'
                   where status = any(%s)""", (list(BUSY),),
            )
            conn.commit()
            self._ready = True

    def _row(self, conn, upload_id: int) -> dict:
        row = conn.execute(f"select {', '.join(_COLUMNS)} from kb_uploads where id=%s", (upload_id,)).fetchone()
        if row is None:
            raise UploadError("There is no such upload", 404)
        return dict(zip(_COLUMNS, row))

    def _set(self, upload_id: int, **values) -> None:
        values = {k: Jsonb(v) if k in ("meta", "plan", "stats") else v for k, v in values.items()}
        sets = ", ".join(f"{k}=%s" for k in values)
        with self.connect() as conn:
            conn.execute(f"update kb_uploads set {sets}, updated_at=now() where id=%s", (*values.values(), upload_id))
            conn.commit()

    def get(self, upload_id: int) -> dict:
        with self.connect() as conn:
            return self._row(conn, upload_id)

    def list(self, limit: int = 100) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                f"select {', '.join(_COLUMNS)} from kb_uploads order by id desc limit %s", (limit,)
            ).fetchall()
        return [dict(zip(_COLUMNS, r)) for r in rows]

    # --- receiving --------------------------------------------------------

    def receive(self, path: Path, filename: str, meta: dict, user: str = "") -> dict:
        """Registers a stored file and starts working on it. Refuses a file
        whose content is already in the knowledge database."""
        sha = file_sha256(path)
        kind, fmt = kind_of(path)
        if kind == "other":
            what = {"binary": "a binary file", "code": "source code", "empty": "an empty file"}.get(fmt, fmt)
            raise UploadError(f"This is {what}: the knowledge database takes PDFs, data files "
                              "(CSV, JSON, Excel, XML, OBO/OWL) and text articles.", 422)
        meta = clean_meta(meta, kind, filename)
        with self.connect() as conn:
            same = conn.execute(
                "select filename, status from kb_uploads where sha256=%s and status <> 'removed'", (sha,)
            ).fetchone()
            if same:
                raise UploadError(f"This file was already uploaded as {same[0]!r} ({same[1]}).")
            registered = conn.execute(
                "select title from kb_sources where files @> %s and status = 'loaded'", (Jsonb([{"sha256": sha}]),)
            ).fetchone()
            if registered:
                raise UploadError(f"This file is already in the knowledge database as {registered[0]!r}.")
            conn.execute("delete from kb_uploads where sha256=%s", (sha,))  # a removed earlier upload
            upload_id = conn.execute(
                """insert into kb_uploads (filename, sha256, bytes, path, kind, status, stage, meta, stats, created_by)
                   values (%s,%s,%s,%s,%s,'waiting','Waiting to start',%s,%s,%s) returning id""",
                (filename, sha, path.stat().st_size, str(path), kind, Jsonb(meta), Jsonb({"format": fmt}), user),
            ).fetchone()[0]
            key = f"upload-{upload_id}-{_slug(meta['title'])}"
            conn.execute("update kb_uploads set source_key=%s where id=%s", (key, upload_id))
            conn.commit()
            upload = self._row(conn, upload_id)
        self._start(upload_id, "load" if kind == "pdf" else "plan")
        return upload

    # --- the work, one file at a time --------------------------------------

    def _start(self, upload_id: int, step: str) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:  # a worker thread: hand it to the server's loop
            if self.loop is None:
                raise UploadError("The upload worker is not running; try again", 503) from None
            self.loop.call_soon_threadsafe(self._spawn, upload_id, step)
        else:
            self._spawn(upload_id, step)

    def _spawn(self, upload_id: int, step: str) -> None:
        task = asyncio.get_running_loop().create_task(self._run(upload_id, step))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, upload_id: int, step: str) -> None:
        if self._queue is None:
            self._queue = asyncio.Lock()
        async with self._queue:
            try:
                if step == "plan":
                    await self._plan(upload_id)
                else:
                    await asyncio.to_thread(self._load, upload_id)
            except Exception as e:  # noqa: BLE001 - recorded on the upload
                log.exception("upload %s failed", upload_id)
                message = str(e) if isinstance(e, (UploadError, LlmError)) else f"{type(e).__name__}: {e}"
                try:
                    self._set(upload_id, status="failed", stage="", note=message[:2000])
                except UploadError:
                    log.warning("Could not record the failure of upload %s: the database is unreachable", upload_id)

    async def wait(self) -> None:
        """Waits for every running job (tests)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    def _record_source(self, upload: dict) -> tuple[Path, str]:
        path = Path(upload["path"])
        if not path.exists():
            raise UploadError(f"The stored file is gone ({path.name}); upload it again")
        fmt = upload["stats"].get("format", "")
        if fmt == "xlsx":
            path, fmt = excel_to_csv(path), "csv"
        return path, fmt

    async def _plan(self, upload_id: int) -> None:
        upload = self.get(upload_id)
        self._set(upload_id, status="reading", stage="The AI is working out what the file contains")
        stats = {"format": upload["stats"].get("format", "")}
        if upload["kind"] == "article":
            text = Path(upload["path"]).read_text(encoding="utf-8", errors="replace")
            try:
                record, dropped = await extract_article(self.llm, text)
            except LlmError as e:
                if "article" not in str(e):
                    raise
                self._set(upload_id, status="skipped", stage="", note="Free text that is not an article about one disease.",
                          plan={"summary": "Not an article about one disease", "verdict": "junk", "reason": str(e)})
                return
            staged = apply_plan(ARTICLE_PLAN, [record])
            plan = {**ARTICLE_PLAN.model_dump(), "content": "article", "summary": f"Article about {record['disease']}",
                    "confidence": 0.9, "model": self.llm.name, "article": record}
            stats |= {"preview": staged.summary(), "dropped_not_in_article": dropped,
                      "needs_review": _review_reasons(Plan.model_validate({**ARTICLE_PLAN.model_dump(), "confidence": 0.9}), staged)}
            self._set(upload_id, status="planned", stage="", plan=plan, stats=stats, note="")
            return
        path, fmt = self._record_source(upload)
        sniffed = sniff(path)
        plan = await make_plan(self.llm, upload["filename"], sniffed)
        stats |= {"delimiter": sniffed.delimiter, "record_path": sniffed.record_path, "read_as": fmt}
        if plan.verdict != "usable":
            self._set(upload_id, status="skipped", stage="", plan=plan.model_dump(), stats=stats,
                      note=plan.reason or plan.summary or "Nothing in this file can be loaded")
            return
        staged = apply_plan(plan, _records(path, fmt, stats), limit=PREVIEW_RECORDS)
        stats |= {"preview": staged.summary(), "needs_review": _review_reasons(plan, staged)}
        self._set(upload_id, status="planned", stage="", plan=plan.model_dump(), stats=stats, note="")

    async def revise(self, upload_id: int, instruction: str) -> dict:
        upload = self.get(upload_id)
        if upload["kind"] != "records" or upload["status"] not in ("planned", "skipped", "failed"):
            raise UploadError("Only the plan of a data file that is not loaded can be revised")
        path, fmt = self._record_source(upload)
        sniffed = sniff(path)
        previous = Plan.model_validate({k: v for k, v in upload["plan"].items() if k in Plan.model_fields})
        plan = await make_plan(self.llm, upload["filename"], sniffed, revise=(previous, instruction))
        stats = {**upload["stats"], "revised": [*upload["stats"].get("revised", []), instruction]}
        if plan.verdict == "usable":
            staged = apply_plan(plan, _records(path, fmt, stats), limit=PREVIEW_RECORDS)
            stats |= {"preview": staged.summary(), "needs_review": _review_reasons(plan, staged)}
            self._set(upload_id, status="planned", plan=plan.model_dump(), stats=stats, note="")
        else:
            self._set(upload_id, status="skipped", plan=plan.model_dump(), stats=stats,
                      note=plan.reason or plan.summary)
        return self.get(upload_id)

    def approve(self, upload_id: int) -> dict:
        upload = self.get(upload_id)
        if upload["status"] != "planned":
            raise UploadError("Only a file whose plan is ready can be approved")
        self._set(upload_id, status="waiting", stage="Approved; waiting to load", note="")
        self._start(upload_id, "load")
        return self.get(upload_id)

    def reject(self, upload_id: int, reason: str) -> dict:
        upload = self.get(upload_id)
        if upload["status"] == "loaded":
            raise UploadError("This file is loaded; remove it instead")
        if upload["status"] in BUSY:
            raise UploadError("Wait until the current step has finished")
        self._set(upload_id, status="skipped", stage="", note=f"Rejected: {reason}")
        return self.get(upload_id)

    def retry(self, upload_id: int) -> dict:
        upload = self.get(upload_id)
        if upload["status"] not in ("failed", "skipped"):
            raise UploadError("Only a failed or skipped file can be tried again")
        planned = upload["kind"] != "pdf" and upload["plan"].get("verdict") == "usable"
        self._set(upload_id, status="waiting", stage="Waiting to start", note="")
        self._start(upload_id, "load" if upload["kind"] == "pdf" or planned else "plan")
        return self.get(upload_id)

    def set_reports(self, upload_id: int, allowed: bool) -> dict:
        """Whether reports may use this file (its licence allows it). Takes
        effect at once: the searches re-read the allowed sources."""
        upload = self.get(upload_id)
        if upload["status"] in BUSY:
            raise UploadError("Wait until the current step has finished")
        with self.connect() as conn:
            conn.execute("update kb_sources set production_allowed=%s where key=%s", (allowed, upload["source_key"]))
            conn.execute("update kb_uploads set meta = meta || %s, updated_at=now() where id=%s",
                         (Jsonb({"production_allowed": allowed}), upload_id))
            conn.commit()
        if upload["status"] == "loaded":
            if upload["kind"] == "pdf" and self.retriever is not None:
                try:
                    self.retriever.save_snapshot()
                except Exception as e:  # noqa: BLE001 - the online search works without it
                    log.warning("Offline snapshot not saved: %s", e)
            if self.on_loaded:
                self.on_loaded()
        return self.get(upload_id)

    def remove(self, upload_id: int) -> dict:
        """Takes the file's rows out of the knowledge database (the source and
        everything that came from it)."""
        upload = self.get(upload_id)
        if upload["status"] in BUSY:
            raise UploadError("Wait until the current step has finished")
        with self.connect() as conn:
            conn.execute("delete from kb_sources where key=%s", (upload["source_key"],))
            conn.execute("delete from kb_drugs where sources = '{}'")
            conn.commit()
        self._set(upload_id, status="removed", stage="", note="Removed from the knowledge database")
        if upload["status"] == "loaded":
            self._after_change(upload_id, snapshot=upload["kind"] == "pdf", final="removed")
        return self.get(upload_id)

    def _load(self, upload_id: int) -> None:
        """Reads (PDF) or transforms (data, article) and loads; then links,
        embeds and refreshes the searches. Runs in a worker thread."""
        upload = self.get(upload_id)
        source = source_for(upload)
        files = [{"name": upload["filename"], "sha256": upload["sha256"], "bytes": upload["bytes"]}]
        started = time.time()
        if upload["kind"] == "pdf":
            from .readers import guideline

            self._set(upload_id, status="loading", stage="Reading the PDF page by page (picture pages by Gemini vision)")
            bundle = guideline.read(source, [Path(upload["path"])], settings=self.settings)
        else:
            self._set(upload_id, status="loading", stage="Applying the approved plan to every record")
            if upload["kind"] == "article":
                staged = apply_plan(ARTICLE_PLAN, [upload["plan"]["article"]])
            else:
                path, fmt = self._record_source(upload)
                plan = Plan.model_validate({k: v for k, v in upload["plan"].items() if k in Plan.model_fields})
                staged = apply_plan(plan, _records(path, fmt, upload["stats"]))
            if not any(staged.entities.values()):
                raise UploadError("Nothing to load: no record produced a valid row.")
            if staged.reject_rate > MAX_REJECT_RATE:
                raise UploadError(f"{staged.reject_rate:.0%} of values failed validation (limit {MAX_REJECT_RATE:.0%}). "
                                  "The mapping is probably wrong; nothing was loaded. Revise the plan.")
            bundle = bundle_from_staged(staged)
        if not any(bundle.rows.values()):
            raise UploadError("Nothing could be read from this file.")
        self._set(upload_id, stage="Saving into the knowledge database")
        with self.connect() as conn:
            try:
                stats = loader.load(conn, source, bundle, files)
            except Exception as e:
                loader.mark_failed(conn, source, f"{type(e).__name__}: {e}")
                raise
            self._set(upload_id, stage="Connecting it to conditions and medicines")
            loader.link(conn)
            quarantined = conn.execute(
                "select count(*) from kb_quarantine q join kb_sources s on s.id=q.source_id where s.key=%s",
                (source.key,),
            ).fetchone()[0]
        stats = {k: v for k, v in stats.items() if k != "kb_quarantine"} | {"quarantined": quarantined,
                                                                             "seconds": round(time.time() - started)}
        self._set(upload_id, stats={**upload["stats"], "loaded": stats})
        self._after_change(upload_id, snapshot=upload["kind"] == "pdf", final="loaded")

    def _after_change(self, upload_id: int, snapshot: bool, final: str) -> None:
        """Passages get their search vectors and the offline copy is saved
        again; the symptom index is told to re-read."""
        note = ""
        if snapshot:
            from .embed import MODELS, embed_missing

            if (MODELS / "article-encoder" / "model.onnx").exists():
                if final == "loaded":
                    self._set(upload_id, status="loading", stage="Computing search vectors for the new passages")
                    with self.connect() as conn:
                        embed_missing(conn, url=self.url)
            elif final == "loaded":
                note = "Loaded. The passages have no search vectors yet: the MedCPT models are missing on this server."
            if self.retriever is not None:
                self._set(upload_id, status="loading" if final == "loaded" else final,
                          stage="Saving the offline copy of the guideline search")
                try:
                    self.retriever.save_snapshot()
                except Exception as e:  # noqa: BLE001 - the online search works without it
                    log.warning("Offline snapshot not saved: %s", e)
                    note = note or f"Loaded; the offline copy was not updated ({type(e).__name__})."
        if self.on_loaded:
            self.on_loaded()
        self._set(upload_id, status=final, stage="", note=note or ("Removed from the knowledge database" if final == "removed" else ""))


def _records(path: Path, fmt: str, stats: dict):
    if fmt == "csv":
        return records.iter_csv(path, stats.get("delimiter"))
    if fmt == "json":
        return records.iter_json(path, stats.get("record_path"))
    if fmt == "obo":
        return records.iter_obo(path)
    if fmt == "owl":
        return records.iter_owl(path)
    if fmt == "xml":
        return records.iter_xml(path, stats.get("record_path"))
    raise UploadError(f"Cannot read records from a {fmt} file")


def _review_reasons(plan: Plan, staged) -> list[str]:
    reasons = []
    if plan.confidence < REVIEW_BELOW_CONFIDENCE:
        reasons.append(f"model confidence is {plan.confidence:.2f}")
    if staged.reject_rate > MAX_REJECT_RATE:
        reasons.append(f"{staged.reject_rate:.0%} of sampled values fail validation; the mapping may be wrong")
    if not any(staged.entities.values()):
        reasons.append("the sample produced nothing to load")
    if not staged.links and not staged.precautions:
        for table, drafts in staged.entities.items():
            creating = sum(d.create for d in drafts.values())
            if creating >= FLOOD_THRESHOLD:
                reasons.append(
                    f"would add thousands of standalone {table} not tied to any disease "
                    f"({creating:,} in the first {staged.records:,} records); consider revising to enrich_only"
                )
    return reasons


def ensure_legacy(url: str, settings=None) -> bool:
    """Loads Medora's earlier knowledge (source medora-legacy, exported from
    Supabase) into the knowledge database once, if it is not there yet.
    True when it is there (or there is nothing to load); False when the
    database could not be reached, so the caller tries again later."""
    from .sources import BY_KEY

    source = BY_KEY.get("medora-legacy")
    if not url or source is None:
        return True
    path = Path(__file__).resolve().parents[3] / source.files[0]
    if not path.exists():
        return True
    try:
        conn = loader.connect(url)
    except Exception:  # noqa: BLE001 - unreachable: try again later
        return False
    with conn:
        try:
            loader.init_schema(conn)
        except SystemExit as e:
            log.warning("Knowledge tables cannot be created: %s", e)
            return True
        if conn.execute("select 1 from kb_sources where key=%s and status='loaded'", (source.key,)).fetchone():
            return True
        from .readers import legacy

        files = [{"name": path.name, "sha256": file_sha256(path), "bytes": path.stat().st_size}]
        stats = loader.load(conn, source, legacy.read(source, [path]), files)
        loader.link(conn)
    log.info("Loaded Medora's earlier knowledge into the knowledge database: %s", stats)
    return True
