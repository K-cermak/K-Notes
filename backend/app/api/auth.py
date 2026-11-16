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
)
from app.services import accounts, invites, sessions

router = APIRouter(prefix="/auth", tags=["auth"])


def _sign_in(db: DbSession, settings: Settings, request: Request, response: Response, user: User) -> Me:
    token = sessions.create(
        db,
        settings,
        user,
        method="password",
        user_agent=request.headers.get("user-agent"),
        ip=client_ip(request),
    )
    db.commit()
    set_session_cookie(response, settings, token)
    return accounts.to_me(user)


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup(
    body: SetupRequest, request: Request, response: Response, db: DbSession, settings: AppSettings
) -> Me:
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
) -> Me:
    user = accounts.authenticate(
        db, throttle, email=body.email, password=body.password, ip=client_ip(request)
    )
    return _sign_in(db, settings, request, response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth: CurrentAuth, response: Response, db: DbSession, settings: AppSettings) -> None:
    sessions.revoke(db, auth.user, auth.session.id)
    clear_session_cookie(response, settings)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest, request: Request, response: Response, db: DbSession, settings: AppSettings
) -> Me:
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
