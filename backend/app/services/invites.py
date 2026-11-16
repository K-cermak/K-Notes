import uuid
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError, ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from app.models import Invite, User
from app.schemas.admin import CreatedLink, PendingInvite
from app.services import accounts, clock, credentials, instance
from app.services.clock import DAY_MS

INVITE_LIFETIME_MS = 7 * DAY_MS
RESET_LIFETIME_MS = DAY_MS

Purpose = Literal["invite", "reset"]


class InvalidLinkError(AppError):
    def __init__(self) -> None:
        super().__init__(404, "invalid_link", "This link is invalid, has expired or has already been used")


def _create(
    db: Session,
    settings: Settings,
    *,
    purpose: Purpose,
    created_by: User | None,
    email: str | None = None,
    user_id: str | None = None,
) -> CreatedLink:
    token = credentials.new_token()
    now = clock.now_ms()
    lifetime = INVITE_LIFETIME_MS if purpose == "invite" else RESET_LIFETIME_MS
    invite = Invite(
        id=str(uuid.uuid4()),
        token_hash=credentials.hash_token(token),
        purpose=purpose,
        email=email,
        user_id=user_id,
        created_by=created_by.id if created_by else None,
        created_at=now,
        expires_at=now + lifetime,
    )
    db.add(invite)
    db.commit()
    path = "invite" if purpose == "invite" else "reset"
    return CreatedLink(id=invite.id, url=f"{settings.base_url}/{path}/{token}", expires_at=invite.expires_at)


def create_invite(db: Session, settings: Settings, admin: User, email: str | None) -> CreatedLink:
    normalized = accounts.normalize_email(email) if email else None
    if normalized and accounts.get_by_email(db, normalized):
        raise ConflictError("email_taken", "An account with this e-mail address already exists")
    return _create(db, settings, purpose="invite", created_by=admin, email=normalized)


def create_reset_link(db: Session, settings: Settings, admin: User | None, user_id: str) -> CreatedLink:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError()
    # Only the newest reset link for a user works.
    db.execute(
        update(Invite)
        .where(Invite.purpose == "reset", Invite.user_id == user.id, Invite.used_at.is_(None))
        .values(used_at=clock.now_ms())
    )
    return _create(db, settings, purpose="reset", created_by=admin, email=user.email, user_id=user.id)


def _find(db: Session, token: str, purpose: Purpose) -> Invite:
    invite = db.scalar(select(Invite).where(Invite.token_hash == credentials.hash_token(token)))
    if invite is None or invite.purpose != purpose or invite.used_at is not None:
        raise InvalidLinkError()
    if invite.expires_at <= clock.now_ms():
        raise InvalidLinkError()
    return invite


def invite_email(db: Session, token: str) -> str | None:
    return _find(db, token, "invite").email


def accept_invite(db: Session, token: str, *, email: str | None, display_name: str, password: str) -> User:
    invite = _find(db, token, "invite")
    chosen = invite.email or email
    if not chosen:
        raise InvalidInputError("invalid_email", "Enter a valid e-mail address")
    user = accounts.create_user(db, email=chosen, display_name=display_name, password=password)
    invite.used_at = clock.now_ms()
    return user


def register(db: Session, *, email: str, display_name: str, password: str) -> User:
    if not instance.registration_enabled(db):
        raise ForbiddenError("registration_closed", "Registration is closed")
    return accounts.create_user(db, email=email, display_name=display_name, password=password)


def reset_email(db: Session, token: str) -> str | None:
    invite = _find(db, token, "reset")
    user = db.get(User, invite.user_id) if invite.user_id else None
    return user.email if user else None


def reset_password(db: Session, token: str, password: str) -> User:
    invite = _find(db, token, "reset")
    user = db.get(User, invite.user_id) if invite.user_id else None
    if user is None:
        raise InvalidLinkError()
    if not user.is_active:
        raise ForbiddenError("account_disabled", "This account has been deactivated")
    accounts.set_password(db, user, password)
    invite.used_at = clock.now_ms()
    return user


def list_pending(db: Session) -> list[PendingInvite]:
    rows = db.scalars(
        select(Invite)
        .where(Invite.purpose == "invite", Invite.used_at.is_(None), Invite.expires_at > clock.now_ms())
        .order_by(Invite.created_at.desc())
    )
    return [
        PendingInvite(
            id=i.id, email=i.email, created_by=i.created_by, created_at=i.created_at, expires_at=i.expires_at
        )
        for i in rows
    ]


def revoke_invite(db: Session, invite_id: str) -> None:
    invite = db.get(Invite, invite_id)
    if invite is None or invite.purpose != "invite":
        raise NotFoundError()
    db.delete(invite)
    db.commit()
