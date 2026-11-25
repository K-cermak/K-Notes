"""Instance limits an admin sets in the administration (SPEC 3): trash retention, image size, sessions."""

from sqlalchemy.orm import Session

from app.models import Setting

TRASH_RETENTION_DAYS = "trash_retention_days"
MAX_IMAGE_MB = "max_image_mb"
SESSION_DAYS = "session_days"

DEFAULTS = {TRASH_RETENTION_DAYS: 7, MAX_IMAGE_MB: 10, SESSION_DAYS: 180}


def _get(db: Session, key: str) -> int:
    row = db.get(Setting, key)
    return int(row.value) if row is not None else DEFAULTS[key]


def set_value(db: Session, key: str, value: int) -> None:
    db.merge(Setting(key=key, value=str(value)))


def trash_retention_days(db: Session) -> int:
    """0 keeps notes in the trash until they are deleted by hand."""
    return _get(db, TRASH_RETENTION_DAYS)


def max_image_mb(db: Session) -> int:
    return _get(db, MAX_IMAGE_MB)


def session_days(db: Session) -> int:
    return _get(db, SESSION_DAYS)
