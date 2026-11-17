from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.api.deps import SESSION_COOKIE, AppSettings, client_ip, set_session_cookie
from app.config import Settings
from app.db import DbSession
from app.errors import AppError, NotFoundError
from app.models import User
from app.services import oidc, sessions

router = APIRouter(prefix="/auth/oidc", tags=["auth"])


def _client(request: Request, settings: Settings) -> oidc.OidcClient:
    client: oidc.OidcClient | None = getattr(request.app.state, "oidc", None)
    if client is None or not settings.oidc_enabled:
        raise NotFoundError()
    return client


def _safe_next(value: str | None) -> str:
    return value if value and value.startswith("/") and not value.startswith("//") else "/"


def _redirect(url: str) -> RedirectResponse:
    response = RedirectResponse(url, status_code=302)
    response.delete_cookie(oidc.STATE_COOKIE, path=oidc.STATE_COOKIE_PATH)
    return response


@router.get("/login", response_class=RedirectResponse, status_code=302)
def oidc_login(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    next: Annotated[str | None, Query(max_length=500)] = None,
    link: bool = False,
) -> RedirectResponse:
    """Sends the browser to the identity provider. With link, the identity is added to the
    signed-in account instead of signing in."""
    client = _client(request, settings)
    link_user_id: str | None = None
    if link:
        token = request.cookies.get(SESSION_COOKIE)
        found = sessions.resolve(db, token) if token else None
        if found is None:
            return _redirect("/login")
        link_user_id = found[1].id
    flow = oidc.new_flow(_safe_next(next), link_user_id)
    try:
        url = client.authorization_url(flow)
    except AppError as exc:
        return _redirect(f"/login?error={exc.code}")
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        oidc.STATE_COOKIE,
        oidc.encode_flow(settings, flow),
        max_age=oidc.STATE_MAX_AGE_S,
        path=oidc.STATE_COOKIE_PATH,
        httponly=True,
        secure=settings.secure_cookies,
        # Lax still sends it on the provider's top-level redirect back to the callback.
        samesite="lax",
    )
    return response


@router.get("/callback", response_class=RedirectResponse, status_code=302)
def oidc_callback(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    code: Annotated[str | None, Query(max_length=2000)] = None,
    state: Annotated[str | None, Query(max_length=200)] = None,
) -> RedirectResponse:
    """Where the identity provider sends the browser back. Errors end on the login page."""
    client = _client(request, settings)
    failed = "/login"
    try:
        flow = oidc.decode_flow(settings, request.cookies.get(oidc.STATE_COOKIE), state)
        if flow.link_user_id:
            failed = "/settings/security"
        if not code:
            raise oidc.OidcError("oidc_failed", "The identity provider did not sign you in")
        identity = client.identity(code, flow)
        if flow.link_user_id:
            user = db.get(User, flow.link_user_id)
            if user is None:
                raise NotFoundError()
            oidc.link(db, user, identity)
            return _redirect("/settings/security?linked=1")
        user = oidc.resolve_user(db, settings, identity)
    except AppError as exc:
        return _redirect(f"{failed}?error={exc.code}")
    # Second factors are the identity provider's job, so TOTP is not asked for here (SPEC 7).
    token = sessions.create(
        db,
        settings,
        user,
        method="oidc",
        user_agent=request.headers.get("user-agent"),
        ip=client_ip(request),
    )
    db.commit()
    response = _redirect(flow.next)
    set_session_cookie(response, settings, token)
    return response
