from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("oidc_issuer", "oidc_subject"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str | None]
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    totp_secret: Mapped[str | None]
    totp_enabled: Mapped[bool] = mapped_column(default=False)
    totp_last_step: Mapped[int | None]
    oidc_issuer: Mapped[str | None]
    oidc_subject: Mapped[str | None]
    locale: Mapped[str] = mapped_column(String(16), default="en")
    theme: Mapped[str] = mapped_column(String(8), default="system")
    default_view: Mapped[str] = mapped_column(String(8), default="grid")
    seq: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[int]


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    auth_method: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[int]
    last_used_at: Mapped[int]
    expires_at: Mapped[int]
    user_agent: Mapped[str | None] = mapped_column(String(300))
    ip: Mapped[str | None] = mapped_column(String(64))


class Invite(Base):
    """An invite link, or with purpose "reset" a password reset link for user_id."""

    __tablename__ = "invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(8))
    email: Mapped[str | None] = mapped_column(String(320))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[int]
    expires_at: Mapped[int]
    used_at: Mapped[int | None]


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str]
