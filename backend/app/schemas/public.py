from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]


class PublicCaptcha(BaseModel):
    provider: Literal["recaptcha", "turnstile", "hcaptcha", "altcha"]
    site_key: str
    login: bool
    registration: bool = Field(description="Open registration and invite links")


class AltchaChallenge(BaseModel):
    parameters: dict[str, Any]
    signature: str


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
    captcha: PublicCaptcha | None = Field(description="None when no captcha is configured")
