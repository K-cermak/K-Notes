from fastapi import APIRouter, status

from app.api.deps import AppSettings, CurrentAuth
from app.db import DbSession
from app.schemas.account import (
    ApiTokenCreate,
    ApiTokenInfo,
    CreatedApiToken,
    Me,
    PasswordChange,
    ProfileUpdate,
    RecoveryCodes,
    SessionInfo,
    StorageStatus,
    TotpCode,
    TotpDisable,
    TotpSetup,
    TotpStatus,
)
from app.services import accounts, oidc, sessions, storage, tokens, totp

router = APIRouter(prefix="/me", tags=["account"])


@router.get("")
def get_me(auth: CurrentAuth) -> Me:
    return accounts.to_me(auth.user)


@router.patch("")
def update_me(body: ProfileUpdate, auth: CurrentAuth, db: DbSession) -> Me:
    return accounts.to_me(accounts.update_profile(db, auth.user, body))


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, auth: CurrentAuth, db: DbSession) -> None:
    accounts.change_password(
        db, auth.user, current=body.current_password, new=body.new_password, keep_session_id=auth.session.id
    )


@router.get("/sessions")
def list_sessions(auth: CurrentAuth, db: DbSession) -> list[SessionInfo]:
    return sessions.list_for(db, auth.user, auth.session.id)


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
def revoke_other_sessions(auth: CurrentAuth, db: DbSession) -> None:
    sessions.revoke_others(db, auth.user.id, auth.session.id)
    db.commit()


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(session_id: str, auth: CurrentAuth, db: DbSession) -> None:
    sessions.revoke(db, auth.user, session_id)


@router.get("/totp")
def totp_status(auth: CurrentAuth, db: DbSession) -> TotpStatus:
    return TotpStatus(
        enabled=auth.user.totp_enabled, recovery_codes_left=totp.recovery_codes_left(db, auth.user)
    )


@router.post("/totp/setup")
def begin_totp(auth: CurrentAuth, db: DbSession, settings: AppSettings) -> TotpSetup:
    """Starts enrolment: a new secret for the authenticator app, active only once confirmed."""
    secret, uri = totp.begin_enrolment(db, settings, auth.user)
    return TotpSetup(secret=secret, uri=uri)


@router.post("/totp/enable")
def enable_totp(body: TotpCode, auth: CurrentAuth, db: DbSession, settings: AppSettings) -> RecoveryCodes:
    """Confirms enrolment with a code from the app. The recovery codes are shown only now."""
    return RecoveryCodes(codes=totp.confirm_enrolment(db, settings, auth.user, body.code))


@router.post("/totp/recovery-codes")
def renew_recovery_codes(
    body: TotpCode, auth: CurrentAuth, db: DbSession, settings: AppSettings
) -> RecoveryCodes:
    """Replaces all recovery codes; the old ones stop working."""
    return RecoveryCodes(codes=totp.new_recovery_codes(db, settings, auth.user, body.code))


@router.post("/totp/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_totp(body: TotpDisable, auth: CurrentAuth, db: DbSession, settings: AppSettings) -> None:
    totp.disable(db, settings, auth.user, password=body.password, code=body.code)


@router.get("/tokens")
def list_tokens(auth: CurrentAuth, db: DbSession) -> list[ApiTokenInfo]:
    return tokens.list_for(db, auth.user)


@router.post("/tokens", status_code=status.HTTP_201_CREATED)
def create_token(body: ApiTokenCreate, auth: CurrentAuth, db: DbSession) -> CreatedApiToken:
    """Creates an API token. The token itself is in this response only."""
    info, secret = tokens.create(db, auth.user, body)
    return CreatedApiToken(**info.model_dump(), token=secret)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id: str, auth: CurrentAuth, db: DbSession) -> None:
    tokens.revoke(db, auth.user, token_id)


@router.delete("/oidc", status_code=status.HTTP_204_NO_CONTENT)
def unlink_oidc(auth: CurrentAuth, db: DbSession, settings: AppSettings) -> None:
    """Removes the single sign-on identity, unless it is the account's only way to sign in."""
    oidc.unlink(db, settings, auth.user)


@router.get("/storage")
def storage_status(auth: CurrentAuth, db: DbSession) -> StorageStatus:
    """How much the user stores and may store (SPEC 7, Storage quotas)."""
    return storage.status(db, auth.user)
