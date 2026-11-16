"""Admin commands, run inside the container: python -m app.cli <command> <email>."""

import argparse
import sys
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.config import ConfigError, Settings, load_settings
from app.db import Database
from app.errors import AppError
from app.migrations import run_migrations
from app.models import User
from app.schemas.admin import AdminUserUpdate
from app.services import accounts, admin, invites


def _user(db: Session, email: str) -> User:
    user = accounts.get_by_email(db, email)
    if user is None:
        raise AppError(404, "not_found", f"No account with the e-mail address {email}")
    return user


def reset_password(db: Session, settings: Settings, email: str) -> str:
    # A link rather than a password typed here: the user picks their own,
    # and it works over docker exec without a TTY.
    link = invites.create_reset_link(db, settings, None, _user(db, email).id)
    return f"Password reset link for {email}, valid for 24 hours:\n{link.url}"


def disable_totp(db: Session, _settings: Settings, email: str) -> str:
    user = _user(db, email)
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_last_step = None
    db.commit()
    return f"Two-factor authentication is now off for {email}."


def make_admin(db: Session, _settings: Settings, email: str) -> str:
    user = _user(db, email)
    admin.update_user(db, None, user.id, AdminUserUpdate(is_admin=True))
    note = "" if user.is_active else " The account is deactivated; reactivate it in the admin area."
    return f"{email} is now an admin.{note}"


COMMANDS: dict[str, tuple[Callable[[Session, Settings, str], str], str]] = {
    "reset-password": (reset_password, "print a one-time password reset link"),
    "disable-totp": (disable_totp, "turn off two-factor authentication"),
    "make-admin": (make_admin, "grant admin rights"),
}


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        commands.add_parser(name, help=help_text).add_argument("email")
    args = parser.parse_args(argv)
    try:
        settings = settings or load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    db = Database(settings.database_path)
    try:
        run_migrations(db.write_engine)
        with db.writer() as session:
            print(COMMANDS[args.command][0](session, settings, args.email))
    except AppError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    finally:
        db.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
