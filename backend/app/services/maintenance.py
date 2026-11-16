import logging

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AppliedOp, AuthSession, Invite, Note, User
from app.services import clock, merge
from app.services.clock import DAY_MS

logger = logging.getLogger(__name__)

APPLIED_OPS_RETENTION_MS = 30 * DAY_MS


def purge_expired_trash(db: Session, settings: Settings) -> dict[str, int]:
    """Purge notes that sat in the trash longer than the retention period (SPEC 5.7).

    Returns the new change counter of every user whose notes were purged, for the event stream.
    """
    if settings.trash_retention_days == 0:
        return {}
    cutoff = clock.now_ms() - settings.trash_retention_days * DAY_MS
    expired = list(
        db.scalars(
            select(Note).where(
                Note.deleted.is_(False), Note.trashed_at.is_not(None), Note.trashed_at < cutoff
            )
        )
    )
    changed: dict[str, int] = {}
    for note in expired:
        user = db.get(User, note.user_id)
        if user is None:
            continue
        merge.purge_note(db, user, note)
        changed[user.id] = user.seq
    db.commit()
    if expired:
        logger.info("Purged %d notes from the trash", len(expired))
    return changed


def clean_up(db: Session) -> None:
    """Nightly: expired sessions, used or expired links, and old idempotency records."""
    now = clock.now_ms()
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    db.execute(delete(Invite).where(or_(Invite.used_at.is_not(None), Invite.expires_at <= now)))
    db.execute(delete(AppliedOp).where(AppliedOp.created_at < now - APPLIED_OPS_RETENTION_MS))
    db.commit()
