from sqlalchemy import text
from sqlalchemy.orm import Session

from app.branding import get_branding
from app.config import Settings
from app.schemas.public import PublicConfig
from app.version import VERSION


def check_database(session: Session) -> None:
    session.execute(text("SELECT 1"))


def public_config(settings: Settings, _session: Session) -> PublicConfig:
    # Accounts and the registration setting arrive in phase 1; until then every instance needs setup.
    return PublicConfig(
        app_name=get_branding().name,
        version=VERSION,
        setup_required=True,
        registration_open=False,
        password_login_enabled=settings.password_login_enabled,
        oidc_enabled=settings.oidc_enabled,
        oidc_provider_name=settings.oidc_provider_name,
        trash_retention_days=settings.trash_retention_days,
        max_image_mb=settings.max_image_mb,
    )
