from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models import AuthSession, User
from app.schemas.admin import AdminUser, AdminUserUpdate, StorageLimit
from app.services import sessions, storage, totp


def _storage_limit(user: User) -> StorageLimit:
    if user.storage_limit_bytes is None:
        return "default"
    return "unlimited" if user.storage_limit_bytes == storage.UNLIMITED else user.storage_limit_bytes


def _to_admin_user(db: Session, user: User, last_active_at: int | None) -> AdminUser:
    return AdminUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        is_active=user.is_active,
        totp_enabled=user.totp_enabled,
        has_password=user.password_hash is not None,
        oidc_linked=user.oidc_subject is not None,
        created_at=user.created_at,
        last_active_at=last_active_at,
        storage_limit=_storage_limit(user),
        storage_used_bytes=storage.used_bytes(db, user),
        storage_limit_bytes=storage.effective_limit(db, user),
    )


def list_users(db: Session) -> list[AdminUser]:
    last_active = (
        select(AuthSession.user_id, func.max(AuthSession.last_used_at).label("last"))
        .group_by(AuthSession.user_id)
        .subquery()
    )
    rows = db.execute(
        select(User, last_active.c.last)
        .outerjoin(last_active, last_active.c.user_id == User.id)
        .order_by(User.created_at)
    )
    return [_to_admin_user(db, user, last) for user, last in rows]


def _get(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError()
    return user


def _active_admins(db: Session) -> int:
    query = select(func.count()).select_from(User).where(User.is_admin, User.is_active)
    return db.scalar(query) or 0


def _guard(db: Session, actor: User | None, target: User, *, removes_admin: bool) -> None:
    """Refuse changes that lock an admin out or leave the instance without an active admin.

    actor is None for the CLI, which may change any account but still keeps one admin.
    """
    if actor is not None and actor.id == target.id:
        raise ConflictError("self_change", "You cannot do this to your own account here")
    if removes_admin and target.is_admin and target.is_active and _active_admins(db) <= 1:
        raise ConflictError("last_admin", "The instance must keep at least one active admin")


def update_user(db: Session, actor: User | None, user_id: str, update: AdminUserUpdate) -> AdminUser:
    user = _get(db, user_id)
    demote = update.is_admin is False and user.is_admin
    deactivate = update.is_active is False and user.is_active
    if demote or deactivate:
        _guard(db, actor, user, removes_admin=True)
    if update.is_admin is not None:
        user.is_admin = update.is_admin
    if update.is_active is not None:
        user.is_active = update.is_active
    if update.storage_limit is not None:
        limit = update.storage_limit
        user.storage_limit_bytes = (
            None if limit == "default" else storage.UNLIMITED if limit == "unlimited" else limit
        )
    if deactivate:
        sessions.revoke_all(db, user.id)
    db.commit()
    return _to_admin_user(db, user, None)


def reset_totp(db: Session, user_id: str) -> None:
    totp.clear(db, _get(db, user_id))
    db.commit()


def delete_user(db: Session, actor: User | None, user_id: str) -> None:
    user = _get(db, user_id)
    _guard(db, actor, user, removes_admin=True)
    # Sessions, reset links and (later) all note data go with the user through ON DELETE CASCADE.
    db.delete(user)
    db.commit()
