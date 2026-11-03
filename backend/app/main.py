import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from . import background
from .db import make_engine
from .ingest.planner import make_ingest_llm
from .kb.stats import KnowledgeStats
from .kb.uploads import UploadDesk
from .knowledge_base import Embedder, KnowledgeIndex
from .offline import UNREACHABLE, OfflineState
from .panel import LocalPanel, SpecialistPanel
from .progress import ProgressBoard
from .llm import make_llm, make_report_llm, make_offline_llm
from .models import ApiKey, ApiRequestLog
from .hospital import router as hospital
from .patients import models as _patient_tables  # noqa: F401  (tables)
from .doctor import router as doctor
from .handoff import router as handoff
from .routers import admin, auth, core, knowledge_admin, reports, sessions, voice
from .settings import Settings
from .tenancy import ensure_default_tenant, ensure_schema
from .voice import make_voice_provider

log = logging.getLogger("medora")


class _WebApp(StaticFiles):
    """The built web app; a plain 404 while there is no build yet."""

    async def get_response(self, path: str, scope):
        if not Path(self.directory, "index.html").exists():
            from starlette.exceptions import HTTPException

            raise HTTPException(404)
        return await super().get_response(path, scope)


def make_retriever(settings: Settings):
    from .kb.embed import MODELS
    from .kb.retrieve import Retriever

    if not settings.knowledge_database_url:
        return None
    if not (MODELS / "query-encoder" / "model.onnx").exists():
        log.warning("Guideline search is off: the MedCPT models are missing from %s", MODELS)
        return None
    return Retriever(
        settings.knowledge_database_url,
        testing_sources=settings.knowledge_testing_sources,
        community_sources=settings.knowledge_community_sources,
        snapshot_dir=Path(settings.data_dir) / "rag_cache",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        def prepare() -> None:
            ensure_schema(app.state.engine)
            ensure_default_tenant(app.state.engine)

        setup = None
        try:
            prepare()
        except UNREACHABLE as e:
            # No network at startup: start anyway and set up the database
            # (and the knowledge index) as soon as Supabase can be reached.
            if not settings.background_tasks:
                raise
            log.warning("Database unreachable at startup, will retry: %s", str(e).splitlines()[0][:200])

            async def retry() -> None:
                while True:
                    await asyncio.sleep(10)
                    try:
                        await asyncio.to_thread(prepare)
                    except UNREACHABLE:
                        continue
                    log.info("Database reached; setup finished")
                    return

            setup = asyncio.create_task(retry())
        task = None
        if settings.background_tasks:
            # Build the search index now, so the first report does not wait
            # for the symptom embeddings.
            asyncio.get_running_loop().run_in_executor(None, app.state.kb.warm)
            if app.state.retriever is not None:
                asyncio.get_running_loop().run_in_executor(None, app.state.retriever.warm)
            async def move_legacy() -> None:
                # Medora's earlier knowledge (moved out of Supabase) goes into
                # the knowledge database as soon as it can be reached.
                from .kb.uploads import ensure_legacy

                while not await asyncio.to_thread(ensure_legacy, settings.knowledge_database_url, settings):
                    await asyncio.sleep(120)
                app.state.kb.refresh_soon()
                app.state.kb_stats.forget()

            app.state.legacy_task = asyncio.create_task(move_legacy())
            task = asyncio.create_task(
                background.run(
                    app.state.runtime, app.state.engine, settings.cloud_database_url,
                    app.state.offline, settings.force_offline,
                )
            )
        yield
        for running in (task, setup, getattr(app.state, "legacy_task", None)):
            if running:
                running.cancel()
        app.state.engine.dispose()

    app = FastAPI(title="Medora API", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.runtime = background.Runtime()
    app.state.progress = ProgressBoard()
    app.state.report_tasks = {}  # session id -> the report being written
    app.state.llm = make_llm(settings)
    app.state.report_llm = make_report_llm(settings)
    # Without internet: the whole report on the local medical model, and
    # visits held in memory until Supabase can be reached (offline.py).
    app.state.offline = OfflineState()
    app.state.offline_llm = make_offline_llm(settings)
    app.state.offline_panel = LocalPanel(app.state.offline_llm) if app.state.offline_llm else None
    app.state.voice_provider = make_voice_provider(settings)
    # SLOT: the offline pipeline (Whisper -> local model -> Piper) goes here.
    app.state.offline_voice_provider = None
    # All medical knowledge lives in the knowledge database
    # (MEDORA_KNOWLEDGE_DATABASE_URL, app/kb); the app database (Supabase)
    # holds none. The symptom evidence index reads it (with a copy on disk
    # for when it cannot be reached).
    app.state.kb = KnowledgeIndex(
        settings.knowledge_database_url,
        Embedder(settings.ollama_url, settings.ollama_embed_model)
        if settings.ollama_embed_model
        else None,
        Path(settings.data_dir) / "rag_cache",
        testing_sources=settings.knowledge_testing_sources,
        community_sources=settings.knowledge_community_sources,
    )
    # Guideline RAG over the knowledge database (app/kb), with MedCPT; None
    # when the database is not configured or the models are missing.
    app.state.retriever = make_retriever(settings)
    # The Database tab: live counts, and files uploaded into the knowledge
    # database (each becomes a source, read like `python -m app.kb load`).
    app.state.kb_stats = KnowledgeStats(
        settings.knowledge_database_url,
        Path(settings.data_dir) / "kb_summary.json",
        Path(settings.data_dir) / "rag_cache",
        testing=settings.knowledge_testing_sources,
        community=settings.knowledge_community_sources,
    )

    def knowledge_changed() -> None:
        app.state.kb.refresh_soon()
        app.state.kb_stats.forget()

    app.state.uploads = UploadDesk(
        settings.knowledge_database_url,
        make_ingest_llm(settings),
        Path(settings.data_dir) / "knowledge_uploads",
        settings=settings,
        retriever=app.state.retriever,
        on_loaded=knowledge_changed,
    )
    # The panel needs a capable hosted model; offline the report is written
    # by the single local model instead.
    app.state.panel = (
        SpecialistPanel(
            settings.gemini_api_key, settings.gemini_text_model, settings.gemini_panel_model
        )
        if settings.gemini_api_key
        else None
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    @app.middleware("http")
    async def log_api_key_requests(request, call_next):
        """Records every request a client's system makes with an API key."""
        started = time.monotonic()
        response = await call_next(request)
        used = getattr(request.state, "api_key", None)
        if used is not None and app.state.runtime.online:
            api_key_id, tenant_id = used
            try:
                _log_call(api_key_id, tenant_id, request, response, started)
            except Exception:
                log.warning("Could not log an API call", exc_info=True)
        return response

    def _log_call(api_key_id, tenant_id, request, response, started) -> None:
        with Session(app.state.engine) as db:
            db.add(
                ApiRequestLog(
                    api_key_id=api_key_id,
                    tenant_id=tenant_id,
                    method=request.method,
                    path=request.url.path[:300],
                    status=response.status_code,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
            )
            db.execute(update(ApiKey).where(ApiKey.id == api_key_id).values(last_used_at=func.now()))
            db.commit()

    for module in (core, auth, sessions, reports, voice, admin, knowledge_admin):
        app.include_router(module.router)
    app.include_router(sessions.intake_router)
    # The hospital portal, kept apart from the company back office.
    app.include_router(hospital.router)
    app.include_router(hospital.company_router)
    # The doctor portal, and the patient's view of the doctor's result.
    app.include_router(doctor.router)
    app.include_router(doctor.patient_router)
    # Filling the intake on the patient's own phone (QR at the kiosk).
    app.include_router(handoff.router)
    # Last, so every API route above wins: the built web app, for phones (a
    # QR code always points here) and for anyone opening port 8100 directly.
    # check_dir=False: a build made after the server started is served too.
    app.mount("/", _WebApp(directory=settings.web_app_dir, html=True, check_dir=False), name="web")
    return app


app = create_app()
