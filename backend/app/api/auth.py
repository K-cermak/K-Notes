from fastapi import APIRouter, Request, Response, status

from app.api.deps import (
    AppSettings,
    CurrentAuth,
    Throttle,
    clear_session_cookie,
    client_ip,
    set_session_cookie,
)
from app.config import Settings
from app.db import DbSession
from app.errors import AppError, ForbiddenError, TooManyRequestsError, UnauthorizedError
from app.models import User
from app.schemas.account import (
    InviteAccept,
    LinkInfo,
    LoginRequest,
    Me,
    PasswordReset,
    RegisterRequest,
    SetupRequest,
    TokenRequest,
    TotpChallenge,
    TotpLogin,
)
from app.services import accounts, invites, sessions, totp

router = APIRouter(prefix="/auth", tags=["auth"])


def _sign_in(
    db: DbSession,
    settings: Settings,
    request: Request,
    response: Response,
    user: User,
    method: str = "password",
) -> Me:
    token = sessions.create(
        db,
        user,
        method=method,
        user_agent=request.headers.get("user-agent"),
        ip=client_ip(request),
    )
    db.commit()
    set_session_cookie(response, settings, db, token)
    return accounts.to_me(user)


def _require_password_login(settings: Settings) -> None:
    # The form is hidden too, but an OIDC-only instance must not accept passwords at all (SPEC 7).
    if not settings.password_login_enabled:
        raise ForbiddenError("password_login_disabled", "Sign in with single sign-on")


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup(
    body: SetupRequest, request: Request, response: Response, db: DbSession, settings: AppSettings
) -> Me:
    _require_password_login(settings)
    user = accounts.setup_admin(db, email=body.email, display_name=body.display_name, password=body.password)
    return _sign_in(db, settings, request, response, user)


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    throttle: Throttle,
) -> Me | TotpChallenge:
    """Signs in, or with two-factor on returns a pending token for /auth/login/totp."""
    _require_password_login(settings)
    user = accounts.authenticate(
        db, throttle, email=body.email, password=body.password, ip=client_ip(request)
    )
    if user.totp_enabled:
        db.commit()
        return TotpChallenge(pending_token=totp.pending_login_token(settings, user))
    return _sign_in(db, settings, request, response, user)


@router.post("/login/totp")
def login_totp(
    body: TotpLogin,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    throttle: Throttle,
) -> Me:
    """The second step: the pending token from /auth/login with a TOTP or recovery code."""
    user_id = totp.pending_login_user(settings, body.pending_token)
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active or not user.totp_enabled:
        raise AppError(401, "login_expired", "The sign-in has expired. Start again.")
    # Six digits are guessable, so attempts are throttled per account like passwords.
    account, ip = f"totp:{user.id}", client_ip(request)
    retry_after = throttle.retry_after(account, ip)
    if retry_after:
        raise TooManyRequestsError(retry_after)
    if not totp.verify(db, settings, user, body.code):
        throttle.failed(account, ip)
        raise UnauthorizedError("The code is not correct")
    throttle.succeeded(account)
    return _sign_in(db, settings, request, response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth: CurrentAuth, response: Response, db: DbSession, settings: AppSettings) -> None:
    sessions.revoke(db, auth.user, auth.session.id)
    clear_session_cookie(response, settings)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest, request: Request, response: Response, db: DbSession, settings: AppSettings
) -> Me:
    _require_password_login(settings)
    user = invites.register(db, email=body.email, display_name=body.display_name, password=body.password)
    return _sign_in(db, settings, request, response, user)


# Tokens travel in the body rather than the path so they do not end up in access logs.
@router.post("/invite/check")
def check_invite(body: TokenRequest, db: DbSession) -> LinkInfo:
    return LinkInfo(email=invites.invite_email(db, body.token))


@router.post("/invite/accept", status_code=status.HTTP_201_CREATED)
def accept_invite(
    body: InviteAccept, request: Request, response: Response, db: DbSession, settings: AppSettings
) -> Me:
    user = invites.accept_invite(
        db, body.token, email=body.email, display_name=body.display_name, password=body.password
    )
    return _sign_in(db, settings, request, response, user)


@router.post("/password-reset/check")
def check_reset(body: TokenRequest, db: DbSession) -> LinkInfo:
    return LinkInfo(email=invites.reset_email(db, body.token))


@router.post("/password-reset/complete")
def complete_reset(
    body: PasswordReset, request: Request, response: Response, db: DbSession, settings: AppSettings
) -> Me:
    user = invites.reset_password(db, body.token, body.password)
    return _sign_in(db, settings, request, response, user)
