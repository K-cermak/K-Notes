from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request, Response

from app.config import Settings
from app.db import Database, DbSession
from app.errors import ForbiddenError, UnauthorizedError
from app.models import AuthSession, User
from app.services import sessions
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


def get_auth(request: Request, response: Response, db: DbSession, settings: AppSettings) -> Auth:
    token = request.cookies.get(SESSION_COOKIE)
    found = sessions.resolve(db, token) if token else None
    if token is None or found is None:
        raise UnauthorizedError()
    session, user = found
    if sessions.touch_due(session):
        # Its own short write transaction, so plain GET requests can keep their read-only one.
        database: Database = request.app.state.db
        with database.writer() as writer:
            sessions.touch(writer, settings, session.id)
        set_session_cookie(response, settings, token)
    return Auth(user=user, session=session, token=token)


CurrentAuth = Annotated[Auth, Depends(get_auth)]


def get_admin(auth: CurrentAuth) -> Auth:
    if not auth.user.is_admin:
        raise ForbiddenError("not_admin", "Only admins can do this")
    return auth


AdminAuth = Annotated[Auth, Depends(get_admin)]
