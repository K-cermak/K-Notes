from fastapi import APIRouter, Response

from app.api.deps import AppSettings
from app.db import DbSession
from app.schemas.public import HealthResponse, PublicConfig
from app.services import instance

router = APIRouter(tags=["public"])


@router.get("/health")
def health(session: DbSession) -> HealthResponse:
    instance.check_database(session)
    return HealthResponse(status="ok")


# Uptime monitors often probe with HEAD; kept out of the schema so the client types stay as they are.
@router.head("/health", include_in_schema=False)
def health_head(session: DbSession) -> Response:
    instance.check_database(session)
    return Response()


@router.get("/config")
def config(settings: AppSettings, session: DbSession) -> PublicConfig:
    return instance.public_config(settings, session)
