from sqlalchemy import text
from sqlalchemy.orm import Session

from app.branding import get_branding
from app.config import Settings
from app.models import Setting
from app.schemas.admin import InstanceSettings, InstanceSettingsUpdate, InstanceStatus
from app.schemas.public import PublicConfig
from app.services import accounts
from app.version import VERSION

_REGISTRATION = "registration_enabled"


def check_database(db: Session) -> None:
    db.execute(text("SELECT 1"))


def registration_enabled(db: Session) -> bool:
    row = db.get(Setting, _REGISTRATION)
    return row is not None and row.value == "true"


def public_config(settings: Settings, db: Session) -> PublicConfig:
    return PublicConfig(
        app_name=get_branding().name,
        version=VERSION,
        setup_required=accounts.user_count(db) == 0,
        registration_open=registration_enabled(db),
        password_login_enabled=settings.password_login_enabled,
        oidc_enabled=settings.oidc_enabled,
        oidc_provider_name=settings.oidc_provider_name,
        trash_retention_days=settings.trash_retention_days,
        max_image_mb=settings.max_image_mb,
    )


def get_settings(db: Session) -> InstanceSettings:
    return InstanceSettings(registration_enabled=registration_enabled(db))


def update_settings(db: Session, update: InstanceSettingsUpdate) -> InstanceSettings:
    if update.registration_enabled is not None:
        db.merge(Setting(key=_REGISTRATION, value="true" if update.registration_enabled else "false"))
    db.commit()
    return get_settings(db)


def status(settings: Settings, db: Session) -> InstanceStatus:
    return InstanceStatus(
        version=VERSION,
        oidc_enabled=settings.oidc_enabled,
        password_login_enabled=settings.password_login_enabled,
        user_count=accounts.user_count(db),
    )
