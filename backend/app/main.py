"""FastAPI application factory (design §4.1).

Batch 2: registers the /api/v1 routers and the global exception handlers that
map the AppError taxonomy to clean HTTP codes (422/400/503/409) with a
structured ``{error: {codigo, mensaje, correlation_id}}`` body and best-effort
structured log rows tied to correlation_id (design §4.8). Availability is
preserved — handlers are per-request; a corrupt payload never crashes the app.

The app owns its engine + session factory (``app.state``) so tests can inject a
testcontainers engine without monkeypatching global state.
"""

import logging
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api import dashboard, ingest
from app.core.errors import AppError
from app.core.settings import Settings, get_settings
from app.db.engine import get_engine
from app.db.retry import probe_database
from app.services.error_logging import persist_error_log

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup probe (bounded retry, never hangs) + shutdown dispose (design §4.2)."""
    engine: AsyncEngine = app.state.engine
    try:
        await probe_database(engine)
        logger.info("database connectivity probe OK")
    except Exception as exc:  # noqa: BLE001 — probe must never crash boot
        logger.warning("database probe failed at startup: %s", exc)
    yield
    await engine.dispose()


def _cid(exc: AppError | None) -> str | None:
    if exc is None:
        return None
    value = getattr(exc, "correlation_id", None)
    return str(value) if value else None


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Global AppError handler — persists a structured log row, then the body."""
    correlation_id = _cid(exc)
    if correlation_id:
        await persist_error_log(
            request.app.state.session_factory,
            correlation_id=correlation_id,
            codigo=exc.codigo,
            mensaje=exc.mensaje,
            stack_trace=traceback.format_exc(),
        )
    return JSONResponse(status_code=exc.status_code, content=exc.to_body())


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI 422 for header/query/body validation — before body read for headers."""
    mensaje = "; ".join(str(err["msg"]) for err in exc.errors())
    return JSONResponse(
        status_code=422,
        content={"error": {"codigo": "ERR_VALIDATION", "mensaje": mensaje, "correlation_id": None}},
    )


async def _integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Unexpected DB integrity violation → 422 (ingest catches its own TOCTOU races)."""
    logger.error("integrity violation: %s", exc)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "codigo": "ERR_INTEGRITY_VIOLATION",
                "mensaje": "Violación de integridad de datos.",
                "correlation_id": None,
            }
        },
    )


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Shape 4xx (404 unknown resources) into the structured error contract."""
    codigo = "ERR_NOT_FOUND" if exc.status_code == 404 else "ERR_HTTP"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"codigo": codigo, "mensaje": str(exc.detail), "correlation_id": None}},
    )


def _register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(IntegrityError, _integrity_error_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)


def create_app(settings: Settings | None = None, *, engine: AsyncEngine | None = None) -> FastAPI:
    """Application factory; ``settings``/``engine`` injectable for tests."""
    conf = settings or get_settings()
    eng = engine or get_engine()
    app = FastAPI(title=conf.app_name, version="0.1.0", lifespan=lifespan)
    app.state.engine = eng
    app.state.session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=conf.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _register_exception_handlers(app)
    app.include_router(ingest.router, prefix="/api/v1")
    app.include_router(dashboard.router, prefix="/api/v1")
    return app


app = create_app()
