"""Two-step login with TOTP and one-time recovery codes (SPEC 7)."""

import base64
import hashlib
import hmac
import secrets
import uuid

from cryptography.fernet import Fernet, InvalidToken
from pyotp import random_base32
from pyotp.totp import TOTP
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.branding import get_branding
from app.config import Settings
from app.errors import ConflictError, InvalidInputError
from app.models import RecoveryCode, User
from app.services import clock, credentials

RECOVERY_CODE_COUNT = 10
PENDING_LOGIN_MS = 5 * 60 * 1000
# Codes from the previous and next 30-second step are accepted, for clocks that drift a little.
DRIFT_STEPS = 1


def _fernet(settings: Settings) -> Fernet:
    key = credentials.derive_key(settings.resolved_secret_key, "totp-secret")
    return Fernet(base64.urlsafe_b64encode(key))


def _secret(settings: Settings, user: User) -> str:
    if user.totp_secret is None:
        raise ConflictError("totp_not_started", "Two-factor authentication has not been set up")
    try:
        return _fernet(settings).decrypt(user.totp_secret.encode()).decode()
    except InvalidToken as exc:
        # The secret key changed since enrolment; only an admin reset helps now.
        raise ConflictError("totp_unreadable", "The two-factor secret cannot be read") from exc


def _matching_step(secret: str, code: str, last_step: int | None) -> int | None:
    """The time step the code belongs to, if it is valid and newer than the last one accepted."""
    code = code.replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        return None
    totp = TOTP(secret)
    now = clock.now_ms() // 1000 // totp.interval
    for step in range(now - DRIFT_STEPS, now + DRIFT_STEPS + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(totp.at(step * totp.interval), code):
            return step
    return None


def begin_enrolment(db: Session, settings: Settings, user: User) -> tuple[str, str]:
    """Stores a new secret, not active until confirmed. Returns the secret and its otpauth:// URI."""
    if user.totp_enabled:
        raise ConflictError("totp_enabled", "Two-factor authentication is already on")
    if user.password_hash is None:
        raise ConflictError(
            "no_password", "Accounts that sign in through single sign-on get two-factor there"
        )
    secret = random_base32()
    user.totp_secret = _fernet(settings).encrypt(secret.encode()).decode()
    db.commit()
    uri = TOTP(secret).provisioning_uri(name=user.email, issuer_name=get_branding().name)
    return secret, uri


def confirm_enrolment(db: Session, settings: Settings, user: User, code: str) -> list[str]:
    """Turns TOTP on once the user proves the authenticator works, and returns recovery codes."""
    if user.totp_enabled:
        raise ConflictError("totp_enabled", "Two-factor authentication is already on")
    step = _matching_step(_secret(settings, user), code, None)
    if step is None:
        raise InvalidInputError("invalid_code", "The code is not correct")
    user.totp_enabled = True
    user.totp_last_step = step
    codes = _replace_recovery_codes(db, user)
    db.commit()
    return codes


def _normalize_recovery_code(code: str) -> str:
    return code.replace("-", "").replace(" ", "").lower()


def _replace_recovery_codes(db: Session, user: User) -> list[str]:
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes: list[str] = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = secrets.token_hex(5)
        codes.append(f"{raw[:5]}-{raw[5:]}")
        db.add(
            RecoveryCode(
                id=str(uuid.uuid4()),
                user_id=user.id,
                code_hash=credentials.hash_token(raw),
                used_at=None,
            )
        )
    return codes


def verify(db: Session, settings: Settings, user: User, code: str) -> bool:
    """Checks a TOTP or recovery code and uses it up. The caller commits."""
    step = _matching_step(_secret(settings, user), code, user.totp_last_step)
    if step is not None:
        user.totp_last_step = step
        return True
    recovery = db.scalar(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == credentials.hash_token(_normalize_recovery_code(code)),
            RecoveryCode.used_at.is_(None),
        )
    )
    if recovery is None:
        return False
    recovery.used_at = clock.now_ms()
    return True


def recovery_codes_left(db: Session, user: User) -> int:
    query = select(func.count()).where(RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None))
    return db.scalar(query) or 0


def new_recovery_codes(db: Session, settings: Settings, user: User, code: str) -> list[str]:
    if not user.totp_enabled:
        raise ConflictError("totp_disabled", "Two-factor authentication is off")
    if not verify(db, settings, user, code):
        raise InvalidInputError("invalid_code", "The code is not correct")
    codes = _replace_recovery_codes(db, user)
    db.commit()
    return codes


def disable(db: Session, settings: Settings, user: User, *, password: str, code: str) -> None:
    if not user.totp_enabled:
        raise ConflictError("totp_disabled", "Two-factor authentication is off")
    if not credentials.verify_password(user.password_hash, password):
        raise InvalidInputError("wrong_password", "The current password is not correct")
    if not verify(db, settings, user, code):
        raise InvalidInputError("invalid_code", "The code is not correct")
    clear(db, user)
    db.commit()


def clear(db: Session, user: User) -> None:
    """Turns TOTP off without checks, for the admin reset and the CLI. The caller commits."""
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_last_step = None
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))


# The pending login token is signed rather than stored: it only says "this user passed the password
# step until <time>", and a TOTP code is still needed to turn it into a session.


def _signature(settings: Settings, payload: str) -> str:
    key = credentials.derive_key(settings.resolved_secret_key, "totp-pending-login")
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def pending_login_token(settings: Settings, user: User) -> str:
    payload = f"{user.id}.{clock.now_ms() + PENDING_LOGIN_MS}"
    return f"{payload}.{_signature(settings, payload)}"


def pending_login_user(settings: Settings, token: str) -> str | None:
    """The user ID in a valid, unexpired pending login token."""
    user_id, _, rest = token.partition(".")
    expires, _, signature = rest.partition(".")
    if not expires.isdigit() or int(expires) < clock.now_ms():
        return None
    if not hmac.compare_digest(_signature(settings, f"{user_id}.{expires}"), signature):
        return None
    return user_id
