import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api import public
from app.branding import REPO_ROOT, get_branding
from app.config import Settings, load_settings
from app.db import make_engine, make_session_factory
from app.errors import ErrorResponse, install_error_handlers
from app.migrations import run_migrations
from app.spa import install_spa
from app.version import VERSION

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"
DEFAULT_STATIC_DIR = REPO_ROOT / "frontend" / "dist"


def prepare_data_dir(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "blobs").mkdir(exist_ok=True)
    _ = settings.resolved_secret_key


def create_app(settings: Settings | None = None, static_dir: Path | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        prepare_data_dir(settings)
        engine = make_engine(settings.database_path)
        run_migrations(engine)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        logger.info("Started version %s with data in %s", VERSION, settings.data_dir)
        yield
        engine.dispose()

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
    install_error_handlers(app)
    app.include_router(public.router, prefix=API_PREFIX)
    install_spa(app, static_dir or DEFAULT_STATIC_DIR)
    return app
