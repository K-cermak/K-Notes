"""Storage quotas (SPEC 7, Storage quotas): what a user stores, and how much they may."""

from sqlalchemy import Text, cast, func, select
from sqlalchemy.orm import Session

from app.models import Blob, ChecklistItem, Note, Setting, User
from app.schemas.account import StorageStatus

DEFAULT_LIMIT_KEY = "default_storage_limit_bytes"
UNLIMITED = -1


def used_bytes(db: Session, user: User) -> int:
    """Note text, trash included, plus each of the user's stored images once."""
    note_text = db.scalar(
        select(
            func.coalesce(func.sum(func.length(Note.title) + func.length(cast(Note.content, Text))), 0)
        ).where(Note.user_id == user.id, Note.deleted.is_(False))
    )
    item_text = db.scalar(
        select(func.coalesce(func.sum(func.length(ChecklistItem.text)), 0)).where(
            ChecklistItem.user_id == user.id, ChecklistItem.deleted.is_(False)
        )
    )
    images = db.scalar(select(func.coalesce(func.sum(Blob.size), 0)).where(Blob.user_id == user.id))
    return int(note_text or 0) + int(item_text or 0) + int(images or 0)


def default_limit(db: Session) -> int | None:
    """The instance default in bytes; None when unlimited."""
    row = db.get(Setting, DEFAULT_LIMIT_KEY)
    return int(row.value) if row is not None and row.value else None


def set_default_limit(db: Session, limit: int | None) -> None:
    db.merge(Setting(key=DEFAULT_LIMIT_KEY, value="" if limit is None else str(limit)))


def effective_limit(db: Session, user: User) -> int | None:
    """The limit in bytes that applies to the user; None when unlimited. Admins never have one."""
    if user.is_admin or user.storage_limit_bytes == UNLIMITED:
        return None
    if user.storage_limit_bytes is None:
        return default_limit(db)
    return user.storage_limit_bytes


def status(db: Session, user: User) -> StorageStatus:
    used = used_bytes(db, user)
    limit = effective_limit(db, user)
    return StorageStatus(used_bytes=used, limit_bytes=limit, full=limit is not None and used >= limit)
