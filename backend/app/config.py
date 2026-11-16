import logging
import secrets
from functools import cached_property
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore", frozen=True)

    data_dir: Path = Path("/data")
    base_url: str
    secret_key: str | None = None
    trash_retention_days: int = 7
    max_image_mb: int = 10
    session_days: int = 180
    password_login_enabled: bool = True
    oidc_discovery_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_provider_name: str = "SSO"
    oidc_auto_provision: bool = False
    trusted_proxies: Annotated[list[str], NoDecode] = []
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("must be an absolute http or https URL, such as https://notes.example.com")
        if parts.path not in ("", "/") or parts.query or parts.fragment:
            raise ValueError("must not contain a path, query or fragment")
        return f"{parts.scheme}://{parts.netloc}"

    @field_validator("trusted_proxies", mode="before")
    @classmethod
    def _split_proxies(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _lower_log_level(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @field_validator("trash_retention_days", "max_image_mb", "session_days")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must not be negative")
        return value

    @model_validator(mode="after")
    def _check_login_methods(self) -> Settings:
        if not self.password_login_enabled and not self.oidc_enabled:
            raise ValueError(
                "APP_PASSWORD_LOGIN_ENABLED=false requires OIDC: set APP_OIDC_DISCOVERY_URL, "
                "APP_OIDC_CLIENT_ID and APP_OIDC_CLIENT_SECRET"
            )
        return self

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.oidc_discovery_url and self.oidc_client_id and self.oidc_client_secret)

    @property
    def secure_cookies(self) -> bool:
        return self.base_url.startswith("https://")

    @property
    def database_path(self) -> Path:
        return self.data_dir / "app.db"

    @cached_property
    def resolved_secret_key(self) -> str:
        """The configured key, or one generated on first start and kept in the data directory."""
        if self.secret_key:
            return self.secret_key
        key_file = self.data_dir / "secret.key"
        if key_file.exists():
            return key_file.read_text().strip()
        key = secrets.token_urlsafe(48)
        key_file.touch(mode=0o600)
        key_file.write_text(key)
        logger.info("Generated a new secret key in %s", key_file)
        return key


def load_settings() -> Settings:
    try:
        return Settings()  # pyright: ignore[reportCallIssue]
    except ValidationError as exc:
        problems: list[str] = []
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else ""
            name = f"APP_{field.upper()}" if field else "configuration"
            message = "is required" if error["type"] == "missing" else error["msg"]
            problems.append(f"{name}: {message.removeprefix('Value error, ')}")
        raise ConfigError("Invalid configuration:\n  " + "\n  ".join(problems)) from None
