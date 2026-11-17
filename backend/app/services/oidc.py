"""Single sign-on through one OIDC provider: authorization code flow with PKCE (SPEC 7).

Authlib supplies PKCE and token handling through its JOSE library; the two HTTP requests of the flow
go through httpx2 directly, which lets tests put a fake provider behind a mock transport.
"""

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx2
from authlib.oauth2.rfc7636 import create_s256_code_challenge  # pyright: ignore[reportUnknownVariableType]
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError, ConflictError
from app.models import User
from app.services import accounts, clock, credentials

SCOPES = "openid email profile"
STATE_COOKIE = "oidc_state"
STATE_COOKIE_PATH = "/api/v1/auth/oidc"
STATE_MAX_AGE_S = 10 * 60
_DISCOVERY_TTL_S = 60 * 60
_SIGNING_ALGORITHMS = ["RS256", "RS384", "RS512", "PS256", "ES256", "ES384", "EdDSA"]


class OidcError(AppError):
    """A failed sign-in. The callback turns the code into a message on the login page."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(400, code, message)


@dataclass(frozen=True)
class Provider:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str
    email: str | None
    email_verified: bool
    name: str | None


@dataclass(frozen=True)
class FlowState:
    """What the callback needs to finish what /login started, kept in a signed cookie."""

    state: str
    nonce: str
    verifier: str
    next: str
    link_user_id: str | None
    expires: int


class OidcClient:
    def __init__(self, settings: Settings, transport: httpx2.BaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport
        self._lock = threading.Lock()
        self._provider: tuple[float, Provider] | None = None
        self._keys: KeySet | None = None

    def _get(self, url: str) -> dict[str, Any]:
        with httpx2.Client(transport=self.transport, timeout=10) as client:
            response = client.get(url)
        if response.status_code != 200:
            raise OidcError("oidc_failed", f"The identity provider answered {response.status_code}")
        return response.json()

    def provider(self) -> Provider:
        with self._lock:
            if self._provider and time.monotonic() - self._provider[0] < _DISCOVERY_TTL_S:
                return self._provider[1]
        assert self.settings.oidc_discovery_url
        data = self._get(self.settings.oidc_discovery_url)
        try:
            provider = Provider(
                issuer=data["issuer"],
                authorization_endpoint=data["authorization_endpoint"],
                token_endpoint=data["token_endpoint"],
                jwks_uri=data["jwks_uri"],
            )
        except KeyError as exc:
            raise OidcError("oidc_failed", f"The discovery document has no {exc}") from exc
        with self._lock:
            self._provider = (time.monotonic(), provider)
        return provider

    def _key_set(self, refresh: bool = False) -> KeySet:
        if self._keys is None or refresh:
            self._keys = KeySet.import_key_set(self._get(self.provider().jwks_uri))  # pyright: ignore[reportArgumentType]
        return self._keys

    def authorization_url(self, flow: FlowState) -> str:
        params = {
            "response_type": "code",
            "client_id": self.settings.oidc_client_id,
            "redirect_uri": redirect_uri(self.settings),
            "scope": SCOPES,
            "state": flow.state,
            "nonce": flow.nonce,
            "code_challenge": _code_challenge(flow.verifier),
            "code_challenge_method": "S256",
        }
        return f"{self.provider().authorization_endpoint}?{urlencode(params)}"

    def identity(self, code: str, flow: FlowState) -> Identity:
        """Exchanges the code for tokens and returns who the validated ID token says signed in."""
        provider = self.provider()
        assert self.settings.oidc_client_id and self.settings.oidc_client_secret
        with httpx2.Client(transport=self.transport, timeout=10) as client:
            response = client.post(
                provider.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri(self.settings),
                    "code_verifier": flow.verifier,
                },
                auth=(self.settings.oidc_client_id, self.settings.oidc_client_secret),
            )
        if response.status_code != 200:
            raise OidcError("oidc_failed", f"The token request failed with {response.status_code}")
        id_token = response.json().get("id_token")
        if not isinstance(id_token, str):
            raise OidcError("oidc_failed", "The provider sent no ID token")
        claims = self._validate(id_token, provider, flow.nonce)
        email = claims.get("email")
        return Identity(
            issuer=provider.issuer,
            subject=str(claims["sub"]),
            email=email.strip().lower() if isinstance(email, str) and email.strip() else None,
            email_verified=claims.get("email_verified") is True,
            name=claims.get("name") or claims.get("preferred_username"),
        )

    def _validate(self, id_token: str, provider: Provider, nonce: str) -> dict[str, Any]:
        try:
            try:
                token = jwt.decode(id_token, self._key_set(), algorithms=_SIGNING_ALGORITHMS)
            except JoseError:
                # The provider may have rotated its keys since they were fetched.
                token = jwt.decode(id_token, self._key_set(refresh=True), algorithms=_SIGNING_ALGORITHMS)
            JWTClaimsRegistry(
                now=lambda: clock.now_ms() // 1000,
                leeway=60,
                iss={"essential": True, "value": provider.issuer},
                aud={"essential": True, "value": str(self.settings.oidc_client_id)},
                sub={"essential": True},
                exp={"essential": True},
                nonce={"essential": True, "value": nonce},
            ).validate(token.claims)
        except (JoseError, ValueError) as exc:
            raise OidcError("oidc_failed", f"The ID token is not valid: {exc}") from exc
        return dict(token.claims)


def _code_challenge(verifier: str) -> str:
    return str(create_s256_code_challenge(verifier))  # pyright: ignore[reportUnknownArgumentType]


def redirect_uri(settings: Settings) -> str:
    return f"{settings.base_url}/api/v1/auth/oidc/callback"


def new_flow(next_path: str, link_user_id: str | None) -> FlowState:
    return FlowState(
        state=secrets.token_urlsafe(24),
        nonce=secrets.token_urlsafe(24),
        verifier=secrets.token_urlsafe(48),
        next=next_path,
        link_user_id=link_user_id,
        expires=clock.now_ms() + STATE_MAX_AGE_S * 1000,
    )


def _signature(settings: Settings, payload: bytes) -> str:
    key = credentials.derive_key(settings.resolved_secret_key, "oidc-state")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def encode_flow(settings: Settings, flow: FlowState) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(flow.__dict__).encode())
    return f"{payload.decode()}.{_signature(settings, payload)}"


def decode_flow(settings: Settings, value: str | None, state: str | None) -> FlowState:
    """The flow from the cookie, if it is genuine, unexpired and for this state."""
    payload, _, signature = (value or "").partition(".")
    if not payload or not hmac.compare_digest(_signature(settings, payload.encode()), signature):
        raise OidcError("oidc_failed", "The sign-in could not be matched to this browser")
    flow = FlowState(**json.loads(base64.urlsafe_b64decode(payload)))
    if flow.expires < clock.now_ms() or state is None or not hmac.compare_digest(flow.state, state):
        raise OidcError("oidc_failed", "The sign-in has expired or does not match")
    return flow


def _by_identity(db: Session, identity: Identity) -> User | None:
    return db.scalar(
        select(User).where(User.oidc_issuer == identity.issuer, User.oidc_subject == identity.subject)
    )


def resolve_user(db: Session, settings: Settings, identity: Identity) -> User:
    """Who is signing in, in the order of SPEC 7. Commits any link or new account."""
    user = _by_identity(db, identity)
    if user is None and identity.email and identity.email_verified:
        # Only a verified address links: anyone can put any address into some provider's profile.
        user = accounts.get_by_email(db, identity.email)
        if user is not None:
            user.oidc_issuer, user.oidc_subject = identity.issuer, identity.subject
    if user is None:
        first = accounts.user_count(db) == 0
        if first and settings.password_login_enabled:
            raise OidcError("setup_required", "Set up the instance with the setup form first")
        # With password login off, the first person through SSO sets the instance up as its admin.
        if not (settings.oidc_auto_provision or first):
            raise OidcError("oidc_no_account", "An administrator has to create your account first")
        if not identity.email:
            raise OidcError("oidc_failed", "The identity provider did not share an e-mail address")
        if accounts.get_by_email(db, identity.email) is not None:
            raise ConflictError("email_taken", "An account with this e-mail address already exists")
        user = User(
            id=str(uuid.uuid4()),
            email=accounts.normalize_email(identity.email),
            display_name=(identity.name or identity.email.split("@")[0]).strip()[:100],
            password_hash=None,
            is_admin=first,
            is_active=True,
            oidc_issuer=identity.issuer,
            oidc_subject=identity.subject,
            created_at=clock.now_ms(),
        )
        db.add(user)
    if not user.is_active:
        raise OidcError("account_disabled", "This account has been deactivated")
    db.commit()
    return user


def link(db: Session, user: User, identity: Identity) -> None:
    other = _by_identity(db, identity)
    if other is not None and other.id != user.id:
        raise OidcError("oidc_taken", "This identity is already linked to another account")
    user.oidc_issuer, user.oidc_subject = identity.issuer, identity.subject
    db.commit()


def unlink(db: Session, settings: Settings, user: User) -> None:
    if user.oidc_subject is None:
        return
    if user.password_hash is None or not settings.password_login_enabled:
        raise ConflictError("last_login_method", "Without single sign-on you could not sign in at all")
    user.oidc_issuer = user.oidc_subject = None
    db.commit()
