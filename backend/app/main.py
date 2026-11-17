import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api import admin, auth, blobs, me, notes, public, sync
from app.branding import REPO_ROOT, get_branding
from app.config import Settings, load_settings
from app.db import Database
from app.errors import ErrorResponse, install_error_handlers
from app.migrations import run_migrations
from app.security import SecurityMiddleware, install_log_redaction
from app.services import blobs as blob_store
from app.services import maintenance
from app.services.clock import DAY_MS
from app.services.events import EventHub
from app.services.throttle import LoginThrottle
from app.spa import install_spa
from app.version import VERSION

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"
MAINTENANCE_INTERVAL_S = 60 * 60
DEFAULT_STATIC_DIR = REPO_ROOT / "frontend" / "dist"


def prepare_data_dir(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "blobs").mkdir(exist_ok=True)
    _ = settings.resolved_secret_key


def run_maintenance(app: FastAPI, *, clean_up: bool) -> None:
    db: Database = app.state.db
    settings: Settings = app.state.settings
    with db.writer() as session:
        changed = maintenance.purge_expired_trash(session, settings)
        blob_store.clean_up(session, settings)
        if clean_up:
            maintenance.clean_up(session)
    for user_id, seq in changed.items():
        app.state.events.publish(user_id, seq)


async def _maintenance_loop(app: FastAPI) -> None:
    """Hourly trash purge, and the nightly cleanup once a day (SPEC 5.7 and 7)."""
    last_cleanup = float("-inf")
    while True:
        due = time.monotonic() - last_cleanup >= DAY_MS / 1000
        try:
            await asyncio.to_thread(run_maintenance, app, clean_up=due)
            if due:
                last_cleanup = time.monotonic()
        except Exception:
            logger.exception("Maintenance failed")
        await asyncio.sleep(MAINTENANCE_INTERVAL_S)


def create_app(settings: Settings | None = None, static_dir: Path | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        prepare_data_dir(settings)
        db = Database(settings.database_path)
        run_migrations(db.write_engine)
        app.state.db = db
        task = asyncio.create_task(_maintenance_loop(app))
        logger.info("Started version %s with data in %s", VERSION, settings.data_dir)
        yield
        app.state.events.close()
        task.cancel()
        db.dispose()

    app = FastAPI(
        title=get_branding().name,
        version=VERSION,
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
        responses={"default": {"model": ErrorResponse}},
        generate_unique_id_function=lambda route: route.name,
    )
    app.state.settings = settings
    app.state.throttle = LoginThrottle()
    app.state.events = EventHub()
    install_error_handlers(app)
    install_log_redaction()
    app.add_middleware(SecurityMiddleware, base_url=settings.base_url, docs_path=f"{API_PREFIX}/docs")
    for router in (
        public.router,
        auth.router,
        me.router,
        admin.router,
        sync.router,
        blobs.router,
        notes.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    install_spa(app, static_dir or DEFAULT_STATIC_DIR)
    return app
