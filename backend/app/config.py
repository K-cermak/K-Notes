import ipaddress
import logging
import os
import secrets
from functools import cached_property
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)

MIN_SECRET_KEY_LENGTH = 32
OIDC_VARIABLES = ("APP_OIDC_DISCOVERY_URL", "APP_OIDC_CLIENT_ID", "APP_OIDC_CLIENT_SECRET")


def _check_http_url(value: str, example: str) -> None:
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"must be an absolute http or https URL, such as {example}")


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
        _check_http_url(value, "https://notes.example.com")
        parts = urlsplit(value)
        if parts.path not in ("", "/") or parts.query or parts.fragment:
            raise ValueError("must not contain a path, query or fragment")
        return f"{parts.scheme}://{parts.netloc}"

    @field_validator("oidc_discovery_url")
    @classmethod
    def _check_discovery_url(cls, value: str | None) -> str | None:
        if value:
            _check_http_url(value, "https://id.example.com/.well-known/openid-configuration")
        return value

    @field_validator("secret_key")
    @classmethod
    def _check_secret_key(cls, value: str | None) -> str | None:
        if value is not None and len(value) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"must be at least {MIN_SECRET_KEY_LENGTH} characters; leave it unset to have one generated"
            )
        return value

    @field_validator("trusted_proxies", mode="before")
    @classmethod
    def _split_proxies(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("trusted_proxies")
    @classmethod
    def _check_proxies(cls, value: list[str]) -> list[str]:
        for proxy in value:
            if proxy == "*":
                continue
            try:
                ipaddress.ip_network(proxy, strict=False)
            except ValueError:
                raise ValueError(
                    f"{proxy!r} is not an IP address or network, such as 10.0.0.1 or 172.16.0.0/12"
                ) from None
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _lower_log_level(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @field_validator("trash_retention_days")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must not be negative (0 turns purging off)")
        return value

    @field_validator("max_image_mb", "session_days")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least 1")
        return value

    @model_validator(mode="after")
    def _check_oidc_complete(self) -> Settings:
        values = (self.oidc_discovery_url, self.oidc_client_id, self.oidc_client_secret)
        missing = [name for name, value in zip(OIDC_VARIABLES, values, strict=True) if not value]
        if 0 < len(missing) < len(OIDC_VARIABLES):
            raise ValueError(
                f"OIDC needs all three of {', '.join(OIDC_VARIABLES)}; missing {', '.join(missing)}"
            )
        return self

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


def _check_data_dir(path: Path) -> None:
    """The data directory must exist or be creatable, and be writable by this process."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("")
        probe.unlink()
    except OSError as exc:
        raise ConfigError(
            f"Invalid configuration:\n  APP_DATA_DIR: cannot write to {path} ({exc.strerror}). "
            f"The process runs as user {os.getuid()}; give it the directory, for example with "
            f"chown {os.getuid()}:{os.getgid()} on the host directory mounted there."
        ) from None


def load_settings() -> Settings:
    """Settings from the environment, checked so that a mistake stops the start with a clear message."""
    try:
        settings = Settings()  # pyright: ignore[reportCallIssue]
    except ValidationError as exc:
        problems: list[str] = []
        for error in exc.errors():
            message = "is required" if error["type"] == "missing" else error["msg"]
            message = message.removeprefix("Value error, ")
            # Checks across several variables name them in their message.
            problems.append(f"APP_{str(error['loc'][0]).upper()}: {message}" if error["loc"] else message)
        raise ConfigError("Invalid configuration:\n  " + "\n  ".join(problems)) from None
    _check_data_dir(settings.data_dir)
    return settings
