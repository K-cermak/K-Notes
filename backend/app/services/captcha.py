"""A captcha on sign-in and registration (SPEC 7): reCAPTCHA v2, Turnstile, hCaptcha or ALTCHA.

The three hosted providers check a token on their own server. ALTCHA is a proof of work that this
server issues and checks itself, so it needs no keys and sends nobody's address to a third party.
"""

import base64
import binascii
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

import altcha
import httpx2
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError, InvalidInputError
from app.models import Setting
from app.schemas.admin import CaptchaPlacement, CaptchaProvider, CaptchaSettings, CaptchaUpdate
from app.schemas.public import AltchaChallenge, PublicCaptcha

logger = logging.getLogger(__name__)

Form = Literal["login", "registration"]

VERIFY_URLS: dict[str, str] = {
    "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    "hcaptcha": "https://api.hcaptcha.com/siteverify",
}

# The widget finds this counter by brute force; each step costs ALTCHA_COST PBKDF2 iterations.
# Tuned so that a phone solves it in about a second.
ALTCHA_COST = 1_000
ALTCHA_MAX_COUNTER = 5_000
ALTCHA_LIFETIME_S = 10 * 60

_KEY = "captcha"


@dataclass(frozen=True)
class CaptchaConfig:
    provider: CaptchaProvider = "none"
    placement: CaptchaPlacement = "both"
    site_key: str = ""
    secret_key: str = ""

    def applies_to(self, form: Form) -> bool:
        return self.provider != "none" and self.placement in (form, "both")


class CaptchaFailedError(AppError):
    def __init__(self) -> None:
        super().__init__(400, "captcha_failed", "Complete the captcha check")


class CaptchaUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(502, "captcha_unavailable", "The captcha service could not be reached")


class CaptchaSecretError(AppError):
    def __init__(self) -> None:
        super().__init__(422, "captcha_secret_invalid", "The captcha provider rejected the secret key")


def load(db: Session) -> CaptchaConfig:
    row = db.get(Setting, _KEY)
    if row is None:
        return CaptchaConfig()
    return CaptchaConfig(**json.loads(row.value))


def _save(db: Session, config: CaptchaConfig) -> None:
    db.merge(Setting(key=_KEY, value=json.dumps(asdict(config))))


def disable(db: Session) -> None:
    _save(db, CaptchaConfig())


def public(db: Session) -> PublicCaptcha | None:
    config = load(db)
    if config.provider == "none":
        return None
    return PublicCaptcha(
        provider=config.provider,
        site_key=config.site_key,
        login=config.applies_to("login"),
        registration=config.applies_to("registration"),
    )


def admin_view(db: Session) -> CaptchaSettings:
    config = load(db)
    return CaptchaSettings(
        provider=config.provider,
        placement=config.placement,
        site_key=config.site_key,
        secret_key_set=bool(config.secret_key),
    )


class CaptchaVerifier:
    """Checks captcha tokens. Holds the HTTP transport (replaced in tests) and ALTCHA's replay guard."""

    def __init__(self, settings: Settings, transport: httpx2.BaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport
        self._lock = threading.Lock()
        self._used: dict[str, float] = {}

    def _altcha_secret(self, purpose: bytes) -> bytes:
        # Derived rather than the secret key itself, so a leaked ALTCHA key reveals nothing else.
        key = self.settings.resolved_secret_key.encode()
        return hmac.new(key, b"altcha-" + purpose, hashlib.sha256).digest()

    def altcha_challenge(self) -> AltchaChallenge:
        # A counter chosen up front lets the server check a solution with one HMAC instead of
        # repeating the work (ALTCHA's deterministic mode).
        challenge = altcha.create_challenge(  # pyright: ignore[reportUnknownMemberType]
            "PBKDF2/SHA-256",
            ALTCHA_COST,
            counter=ALTCHA_MAX_COUNTER // 2 + secrets.randbelow(ALTCHA_MAX_COUNTER // 2),
            expires_at=int(time.time()) + ALTCHA_LIFETIME_S,
            hmac_secret=self._altcha_secret(b"challenge"),
            hmac_key_secret=self._altcha_secret(b"key"),
        )
        data = cast(dict[str, Any], challenge.to_dict())  # pyright: ignore[reportUnknownMemberType]
        return AltchaChallenge(parameters=data["parameters"], signature=data["signature"])

    def verify(self, config: CaptchaConfig, token: str, ip: str, *, testing: bool = False) -> bool:
        """Whether the token is a solved captcha. testing turns a rejected secret key into an error."""
        if config.provider == "altcha":
            return self._verify_altcha(token)
        return self._verify_remote(config, token, ip, testing=testing)

    def _verify_remote(self, config: CaptchaConfig, token: str, ip: str, *, testing: bool) -> bool:
        data = {"secret": config.secret_key, "response": token}
        if ip:
            data["remoteip"] = ip
        if config.provider == "hcaptcha":
            data["sitekey"] = config.site_key
        try:
            with httpx2.Client(transport=self.transport, timeout=10) as client:
                response = client.post(VERIFY_URLS[config.provider], data=data)
            body = response.json() if response.status_code == 200 else None
        except httpx2.HTTPError, ValueError:
            body = None
        if not isinstance(body, dict):
            logger.warning("The %s verification endpoint could not be reached", config.provider)
            raise CaptchaUnavailableError()
        result = cast(dict[str, Any], body)
        if result.get("success") is True:
            return True
        codes: list[Any] = result.get("error-codes") or []
        if "invalid-input-secret" in codes:
            if testing:
                raise CaptchaSecretError()
            # Every sign-in fails until the admin fixes it, so it belongs in the log.
            logger.warning("%s rejects the configured secret key", config.provider)
        return False

    def _verify_altcha(self, token: str) -> bool:
        result = altcha.verify_solution(
            token, self._altcha_secret(b"challenge"), hmac_key_secret=self._altcha_secret(b"key")
        )
        if not result.verified:
            return False
        try:
            parameters = json.loads(base64.b64decode(token))["challenge"]["parameters"]
            nonce, expires_at = str(parameters["nonce"]), float(parameters["expiresAt"])
        except binascii.Error, ValueError, KeyError, TypeError:
            return False
        # A solved challenge stays valid until it expires, so each one counts only once.
        now = time.time()
        with self._lock:
            self._used = {n: exp for n, exp in self._used.items() if exp > now}
            if nonce in self._used:
                return False
            self._used[nonce] = expires_at
        return True


def require(db: Session, verifier: CaptchaVerifier, form: Form, token: str | None, ip: str) -> None:
    config = load(db)
    if config.applies_to(form) and not (token and verifier.verify(config, token, ip)):
        raise CaptchaFailedError()


def update(db: Session, verifier: CaptchaVerifier, change: CaptchaUpdate, ip: str) -> CaptchaSettings:
    """Saves the captcha settings. New keys take effect only with a token solved against them,

    so a typo cannot lock everyone, the admin included, out of signing in.
    """
    current = load(db)
    if change.provider not in VERIFY_URLS:
        _save(db, CaptchaConfig(provider=change.provider, placement=change.placement))
        db.commit()
        return admin_view(db)
    site_key = change.site_key.strip()
    if not site_key:
        raise InvalidInputError("captcha_site_key_required", "Enter the site key")
    secret_key = change.secret_key.strip()
    if not secret_key and current.provider == change.provider:
        secret_key = current.secret_key
    if not secret_key:
        raise InvalidInputError("captcha_secret_key_required", "Enter the secret key")
    new = CaptchaConfig(change.provider, change.placement, site_key, secret_key)
    same_keys = (new.provider, new.site_key, new.secret_key) == (
        current.provider,
        current.site_key,
        current.secret_key,
    )
    if not same_keys and not (change.token and verifier.verify(new, change.token, ip, testing=True)):
        raise CaptchaFailedError()
    _save(db, new)
    db.commit()
    return admin_view(db)
