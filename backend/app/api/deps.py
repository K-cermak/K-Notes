from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import READ_METHODS, Database, DbSession
from app.errors import ForbiddenError, UnauthorizedError
from app.models import ApiToken, AuthSession, User
from app.services import sessions, tokens
from app.services.clock import DAY_MS
from app.services.throttle import LoginThrottle

SESSION_COOKIE = "session"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_throttle(request: Request) -> LoginThrottle:
    return request.app.state.throttle


AppSettings = Annotated[Settings, Depends(get_settings)]
Throttle = Annotated[LoginThrottle, Depends(get_throttle)]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * DAY_MS // 1000,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, secure=settings.secure_cookies, samesite="lax", path="/"
    )


@dataclass
class Auth:
    user: User
    session: AuthSession
    token: str


def _write(request: Request, db: Session, work: Callable[[Session], None]) -> None:
    """Runs a small bookkeeping write while authenticating.

    A read request gets its own short write transaction, so it keeps its read-only one. A write
    request already holds the write lock through db, and a second writer would wait for it in vain.
    """
    if request.method in READ_METHODS:
        database: Database = request.app.state.db
        with database.writer() as writer:
            work(writer)
    else:
        work(db)


def get_auth(request: Request, response: Response, db: DbSession, settings: AppSettings) -> Auth:
    if "authorization" in request.headers:
        raise ForbiddenError("token_not_allowed", "API tokens cannot be used for this")
    token = request.cookies.get(SESSION_COOKIE)
    found = sessions.resolve(db, token) if token else None
    if token is None or found is None:
        raise UnauthorizedError()
    session, user = found
    if sessions.touch_due(session):
        _write(request, db, lambda writer: sessions.touch(writer, settings, session.id))
        set_session_cookie(response, settings, token)
    return Auth(user=user, session=session, token=token)


CurrentAuth = Annotated[Auth, Depends(get_auth)]


def session_user(database: Database, token: str | None) -> tuple[str, int] | None:
    """(user id, change counter) for a valid session, in a short transaction of its own.

    For long-running endpoints (the event stream, uploads), which must not hold a database
    transaction open the way a request-scoped session would.
    """
    if token is None:
        return None
    with database.reader() as db:
        found = sessions.resolve(db, token)
        return (found[1].id, found[1].seq) if found else None


def get_admin(auth: CurrentAuth) -> Auth:
    if not auth.user.is_admin:
        raise ForbiddenError("not_admin", "Only admins can do this")
    return auth


AdminAuth = Annotated[Auth, Depends(get_admin)]


@dataclass
class ApiAuth:
    user: User
    token: ApiToken | None


def get_api_auth(request: Request, response: Response, db: DbSession, settings: AppSettings) -> ApiAuth:
    """For the REST API (SPEC 8): a Bearer token within its scope, or the browser session."""
    header = request.headers.get("authorization")
    if header is None:
        return ApiAuth(user=get_auth(request, response, db, settings).user, token=None)
    scheme, _, secret = header.partition(" ")
    found = tokens.resolve(db, secret.strip()) if scheme.lower() == "bearer" else None
    if found is None:
        raise UnauthorizedError("The token is not valid, has expired or was revoked")
    token, user = found
    if request.method not in READ_METHODS and token.scope != "write":
        raise ForbiddenError("insufficient_scope", "This token can only read")
    if tokens.touch_due(token):
        _write(request, db, lambda writer: tokens.touch(writer, token.id))
    return ApiAuth(user=user, token=token)


CurrentApiAuth = Annotated[ApiAuth, Depends(get_api_auth)]
