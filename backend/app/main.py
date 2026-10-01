import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import callbacks, escalations, health, knowledge, leads, speech, voice_tools
from app.config import Settings
from app.db.session import initialize_database
from app.knowledge.index import KnowledgeIndex
from app.knowledge.pipeline import IngestionPipeline
from app.knowledge.retrieve import KnowledgeService
from app.logging_config import configure_logging
from app.providers.embeddings import create_embedding_provider
from app.providers.llm import create_llm_provider
from app.providers.windows_speech import WindowsSpeechProvider
from app.providers.asr import create_asr_provider
from app.providers.voice import BrowserVoiceProvider
from app.voice.conversation import ConversationService
from app.voice.tools import VoiceTools
from sqlalchemy.orm.exc import StaleDataError

logger = logging.getLogger("darwix.api")


def create_app(settings=None):
    settings = settings or Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app):
        engine, sessions = initialize_database(settings.database_url)
        embedding = create_embedding_provider(settings)
        llm = create_llm_provider(settings)
        index = KnowledgeIndex(settings, embedding)
        try:
            try:
                await asyncio.wait_for(index.ensure(), settings.provider_timeout_seconds)
            except Exception as exc:
                logger.error("startup_index_unavailable", extra={"error_type": type(exc).__name__})
                raise RuntimeError("Qdrant is unavailable. Start docker compose up -d qdrant, or set QDRANT_URL= for embedded mode.") from None
            app.state.sessions = sessions
            app.state.engine = engine
            app.state.knowledge = KnowledgeService(settings, embedding, llm, index, IngestionPipeline(settings, embedding, index))
            app.state.settings = settings
            app.state.voice_tools = VoiceTools(sessions, app.state.knowledge, settings)
            app.state.conversation = ConversationService(app.state.voice_tools, llm, settings)
            app.state.voice = BrowserVoiceProvider(app.state.conversation)
            app.state.asr = create_asr_provider(settings)
            app.state.tts = WindowsSpeechProvider(settings)
            yield
        finally:
            await index.close()
            await embedding.close()
            await llm.close()
            engine.dispose()

    app = FastAPI(title="Darwix assessment — Phases 0–2", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        logger.info("request_complete", extra={"request_id": request.state.request_id,
            "status_code": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 3)})
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={"detail": "Invalid request.",
            "errors": [{"loc": list(error["loc"]), "type": error["type"]} for error in exc.errors()]})

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
        logger.error("unexpected_request_error", extra={"request_id": request_id, "error_type": type(exc).__name__})
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred.", "request_id": request_id},
                            headers={"X-Request-ID": request_id})

    @app.exception_handler(StaleDataError)
    async def concurrent_update(request, exc):
        return JSONResponse(status_code=409, content={"detail":"The call changed concurrently. Refresh it before retrying."})

    app.include_router(health.router)
    app.include_router(knowledge.router)
    for router in (voice_tools.router, leads.router, callbacks.router, escalations.router, speech.router):
        app.include_router(router)
    return app


app = create_app()
