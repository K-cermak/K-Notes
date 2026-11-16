from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class PublicConfig(BaseModel):
    app_name: str
    version: str
    setup_required: bool
    registration_open: bool
    password_login_enabled: bool
    oidc_enabled: bool
    oidc_provider_name: str
    trash_retention_days: int
    max_image_mb: int
