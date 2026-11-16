from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import NotFoundError
from app.models import AuthSession, User
from app.schemas.account import SessionInfo
from app.services import clock, credentials
from app.services.clock import DAY_MS

# Sliding the expiry on every request would turn every read into a write.
TOUCH_INTERVAL_MS = 60 * 60 * 1000


def create(
    db: Session, settings: Settings, user: User, *, method: str, user_agent: str | None, ip: str | None
) -> str:
    """Start a session and return its token, which is only ever stored as a hash."""
    token = credentials.new_token()
    now = clock.now_ms()
    db.add(
        AuthSession(
            id=credentials.hash_token(token),
            user_id=user.id,
            auth_method=method,
            created_at=now,
            last_used_at=now,
            expires_at=now + settings.session_days * DAY_MS,
            user_agent=(user_agent or "")[:300] or None,
            ip=ip,
        )
    )
    return token


def resolve(db: Session, token: str) -> tuple[AuthSession, User] | None:
    row = db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.id == credentials.hash_token(token))
    ).first()
    if row is None:
        return None
    session, user = row
    if session.expires_at <= clock.now_ms() or not user.is_active:
        return None
    return session, user


def touch_due(session: AuthSession) -> bool:
    return clock.now_ms() - session.last_used_at >= TOUCH_INTERVAL_MS


def touch(db: Session, settings: Settings, session_id: str) -> None:
    session = db.get(AuthSession, session_id)
    if session is None:
        return
    now = clock.now_ms()
    session.last_used_at = now
    session.expires_at = now + settings.session_days * DAY_MS
    db.commit()


def list_for(db: Session, user: User, current_id: str) -> list[SessionInfo]:
    rows = db.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.expires_at > clock.now_ms())
        .order_by(AuthSession.last_used_at.desc())
    )
    return [
        SessionInfo(
            id=s.id,
            auth_method=s.auth_method,
            created_at=s.created_at,
            last_used_at=s.last_used_at,
            expires_at=s.expires_at,
            user_agent=s.user_agent,
            ip=s.ip,
            current=s.id == current_id,
        )
        for s in rows
    ]


def revoke(db: Session, user: User, session_id: str) -> None:
    session = db.get(AuthSession, session_id)
    if session is None or session.user_id != user.id:
        raise NotFoundError()
    db.delete(session)
    db.commit()


def revoke_others(db: Session, user_id: str, keep_id: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id, AuthSession.id != keep_id))


def revoke_all(db: Session, user_id: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
