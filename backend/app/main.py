"""FastAPI application factory (design §4.1).

Batch 1: lifespan with a bounded startup DB probe + shutdown dispose, and CORS.
Routers and exception handlers arrive in Batch 2.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import Settings, get_settings
from app.db.engine import get_engine
from app.db.retry import probe_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup probe (bounded retry, never hangs) + shutdown dispose (design §4.2)."""
    engine = get_engine()
    try:
        await probe_database(engine)
        logger.info("database connectivity probe OK")
    except Exception as exc:  # noqa: BLE001 — probe must never crash boot
        logger.warning("database probe failed at startup: %s", exc)
    yield
    await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory; ``settings`` injectable for tests."""
    conf = settings or get_settings()
    app = FastAPI(title=conf.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=conf.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()
