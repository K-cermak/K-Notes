from fastapi import APIRouter

from app.api.deps import AppSettings
from app.db import DbSession
from app.schemas.public import HealthResponse, PublicConfig
from app.services import instance

router = APIRouter(tags=["public"])


@router.get("/health")
def health(session: DbSession) -> HealthResponse:
    instance.check_database(session)
    return HealthResponse(status="ok")


@router.get("/config")
def config(settings: AppSettings, session: DbSession) -> PublicConfig:
    return instance.public_config(settings, session)
