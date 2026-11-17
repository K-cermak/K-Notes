"""OIDC sign-in against a fake identity provider behind a mock transport."""

import base64
import hashlib
import secrets
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey

from app.config import Settings
from app.main import create_app
from app.services import clock
from app.services.oidc import OidcClient
from tests.conftest import ADMIN, FakeClock, setup_admin

ISSUER = "https://idp.test"
CLIENT_ID = "notes"
CLIENT_SECRET = "client-secret"


@dataclass
class Grant:
    claims: dict[str, Any]
    challenge: str
    nonce: str


@dataclass
class FakeProvider:
    key: RSAKey = field(
        default_factory=lambda: RSAKey.generate_key(2048, parameters={"kid": "k1", "alg": "RS256"})
    )
    grants: dict[str, Grant] = field(default_factory=dict[str, Grant])
    # Lets a test break one part of the ID token.
    overrides: dict[str, Any] = field(default_factory=dict[str, Any])

    def authorize(self, url: str, claims: dict[str, Any]) -> str:
        query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        assert url.startswith(f"{ISSUER}/authorize?")
        assert query["client_id"] == CLIENT_ID
        assert query["redirect_uri"] == "http://testserver/api/v1/auth/oidc/callback"
        assert query["code_challenge_method"] == "S256"
        assert set(query["scope"].split()) == {"openid", "email", "profile"}
        code = secrets.token_urlsafe(8)
        self.grants[code] = Grant(claims, query["code_challenge"], query["nonce"])
        return code

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx2.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                },
            )
        if path == "/jwks":
            return httpx2.Response(200, json=KeySet([self.key]).as_dict(private=False))
        if path == "/token":
            expected = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
            if request.headers.get("authorization") != f"Basic {expected}":
                return httpx2.Response(401, json={"error": "invalid_client"})
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            grant = self.grants.pop(form["code"], None)
            verifier_hash = hashlib.sha256(form.get("code_verifier", "").encode()).digest()
            challenge = base64.urlsafe_b64encode(verifier_hash).rstrip(b"=").decode()
            if grant is None or challenge != grant.challenge:
                return httpx2.Response(400, json={"error": "invalid_grant"})
            now = clock.now_ms() // 1000
            claims = {
                "iss": ISSUER,
                "aud": CLIENT_ID,
                "iat": now,
                "exp": now + 300,
                "nonce": grant.nonce,
                **grant.claims,
                **self.overrides,
            }
            id_token = jwt.encode({"alg": "RS256", "kid": "k1"}, claims, self.key)
            return httpx2.Response(
                200, json={"access_token": "x", "token_type": "Bearer", "id_token": id_token}
            )
        return httpx2.Response(404)


@contextmanager
def instance(tmp_path: Path, **overrides: Any) -> Generator[tuple[TestClient, FakeProvider]]:
    settings = Settings(
        base_url="http://testserver",
        data_dir=tmp_path / "data",
        oidc_discovery_url=f"{ISSUER}/.well-known/openid-configuration",
        oidc_client_id=CLIENT_ID,
        oidc_client_secret=CLIENT_SECRET,
        oidc_provider_name="Company SSO",
        **overrides,
    )
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<!doctype html>")
    app = create_app(settings, static_dir=dist)
    provider = FakeProvider()
    app.state.oidc = OidcClient(settings, transport=httpx2.MockTransport(provider.handle))
    with TestClient(app) as client:
        yield client, provider


def person(sub: str = "u-1", email: str = "ola@example.com", verified: bool = True) -> dict[str, Any]:
    return {"sub": sub, "email": email, "email_verified": verified, "name": "Ola Nordmann"}


def sign_in(
    client: TestClient, provider: FakeProvider, claims: dict[str, Any], **params: str
) -> httpx2.Response:
    start = client.get("/api/v1/auth/oidc/login", params=params, follow_redirects=False)
    assert start.status_code == 302, start.text
    location = start.headers["location"]
    code = provider.authorize(location, claims)
    state = parse_qs(urlsplit(location).query)["state"][0]
    return client.get(
        "/api/v1/auth/oidc/callback", params={"code": code, "state": state}, follow_redirects=False
    )


def error_of(response: httpx2.Response) -> str | None:
    return parse_qs(urlsplit(response.headers["location"]).query).get("error", [None])[0]


def test_an_unknown_user_is_refused_without_auto_provisioning(tmp_path: Path) -> None:
    with instance(tmp_path) as (client, provider):
        setup_admin(client)
        client.cookies.clear()
        response = sign_in(client, provider, person())
        assert response.headers["location"] == "/login?error=oidc_no_account"
        assert client.get("/api/v1/me").status_code == 401


def test_auto_provisioning_creates_the_account(tmp_path: Path) -> None:
    with instance(tmp_path, oidc_auto_provision=True) as (client, provider):
        setup_admin(client)
        client.cookies.clear()
        response = sign_in(client, provider, person(), next="/archive")
        assert response.headers["location"] == "/archive"
        me = client.get("/api/v1/me").json()
        assert (me["email"], me["display_name"], me["is_admin"]) == ("ola@example.com", "Ola Nordmann", False)
        assert (me["oidc_linked"], me["has_password"]) == (True, False)
        assert client.get("/api/v1/me/sessions").json()[0]["auth_method"] == "oidc"


def test_a_linked_user_is_found_by_subject_even_with_a_new_address(tmp_path: Path) -> None:
    with instance(tmp_path, oidc_auto_provision=True) as (client, provider):
        setup_admin(client)
        client.cookies.clear()
        sign_in(client, provider, person())
        client.cookies.clear()
        sign_in(client, provider, person(email="ola@new.example.com"))
        assert client.get("/api/v1/me").json()["email"] == "ola@example.com"


def test_a_verified_address_links_the_local_account(tmp_path: Path) -> None:
    with instance(tmp_path) as (client, provider):
        setup_admin(client)
        client.cookies.clear()
        sign_in(client, provider, person(sub="admin-at-idp", email=ADMIN["email"].upper()))
        me = client.get("/api/v1/me").json()
        assert (me["email"], me["oidc_linked"], me["is_admin"]) == (ADMIN["email"], True, True)


def test_an_unverified_address_never_links(tmp_path: Path) -> None:
    with instance(tmp_path, oidc_auto_provision=True) as (client, provider):
        setup_admin(client)
        client.cookies.clear()
        response = sign_in(client, provider, person(email=ADMIN["email"], verified=False))
        assert error_of(response) == "email_taken"
        assert client.get("/api/v1/me").status_code == 401


def test_oidc_sign_in_skips_totp(tmp_path: Path, fake_clock: FakeClock) -> None:
    from pyotp.totp import TOTP

    with instance(tmp_path) as (client, provider):
        setup_admin(client)
        secret = client.post("/api/v1/me/totp/setup").json()["secret"]
        client.post("/api/v1/me/totp/enable", json={"code": TOTP(secret).at(fake_clock.now // 1000)})
        client.cookies.clear()
        sign_in(client, provider, person(sub="a", email=ADMIN["email"]))
        assert client.get("/api/v1/me").json()["totp_enabled"] is True


def test_a_deactivated_account_is_refused(tmp_path: Path) -> None:
    with instance(tmp_path, oidc_auto_provision=True) as (client, provider):
        setup_admin(client)
        admin_cookies = dict(client.cookies)
        client.cookies.clear()
        sign_in(client, provider, person())
        user_id = client.get("/api/v1/me").json()["id"]
        client.cookies.clear()
        client.cookies.update(admin_cookies)
        client.patch(f"/api/v1/admin/users/{user_id}", json={"is_active": False})
        client.cookies.clear()
        assert error_of(sign_in(client, provider, person())) == "account_disabled"


@pytest.mark.parametrize(
    ("override", "tamper"),
    [
        ({"aud": "someone-else"}, None),
        ({"iss": "https://evil.test"}, None),
        ({"nonce": "replayed"}, None),
        ({"exp": 1}, None),
        ({}, "state"),
        ({}, "cookie"),
    ],
)
def test_forged_or_mismatched_responses_are_refused(
    tmp_path: Path, override: dict[str, Any], tamper: str | None
) -> None:
    with instance(tmp_path, oidc_auto_provision=True) as (client, provider):
        setup_admin(client)
        client.cookies.clear()
        provider.overrides = override
        start = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
        code = provider.authorize(start.headers["location"], person())
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        if tamper == "state":
            state = "other"
        if tamper == "cookie":
            client.cookies.clear()
        response = client.get(
            "/api/v1/auth/oidc/callback", params={"code": code, "state": state}, follow_redirects=False
        )
        assert error_of(response) == "oidc_failed"
        assert client.get("/api/v1/me").status_code == 401


def test_a_token_signed_by_another_key_is_refused(tmp_path: Path) -> None:
    with instance(tmp_path, oidc_auto_provision=True) as (client, provider):
        setup_admin(client)
        client.cookies.clear()
        start = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
        code = provider.authorize(start.headers["location"], person())
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        # The token endpoint now signs with a key the published key set does not contain.
        provider.key, published = (
            RSAKey.generate_key(2048, parameters={"kid": "k1", "alg": "RS256"}),
            provider.key,
        )
        original = provider.handle

        def handle(request: httpx2.Request) -> httpx2.Response:
            if request.url.path == "/jwks":
                return httpx2.Response(200, json=KeySet([published]).as_dict(private=False))
            return original(request)

        cast(Any, client.app).state.oidc.transport = httpx2.MockTransport(handle)
        response = client.get(
            "/api/v1/auth/oidc/callback", params={"code": code, "state": state}, follow_redirects=False
        )
        assert error_of(response) == "oidc_failed"


def test_with_password_login_off_the_first_sso_user_becomes_admin(tmp_path: Path) -> None:
    with instance(tmp_path, password_login_enabled=False) as (client, provider):
        assert client.get("/api/v1/config").json()["setup_required"] is True
        refused = client.post("/api/v1/auth/setup", json=ADMIN)
        assert (refused.status_code, refused.json()["code"]) == (403, "password_login_disabled")
        sign_in(client, provider, person())
        assert client.get("/api/v1/me").json()["is_admin"] is True
        login = client.post("/api/v1/auth/login", json={"email": "ola@example.com", "password": "x" * 12})
        assert login.json()["code"] == "password_login_disabled"
        # Only the first one: later unknown users still need an account or auto-provisioning.
        client.cookies.clear()
        assert (
            error_of(sign_in(client, provider, person(sub="u-2", email="b@example.com"))) == "oidc_no_account"
        )


def test_with_password_login_on_setup_goes_through_the_form(tmp_path: Path) -> None:
    with instance(tmp_path, oidc_auto_provision=True) as (client, provider):
        assert error_of(sign_in(client, provider, person())) == "setup_required"


def test_link_and_unlink_in_settings(tmp_path: Path) -> None:
    with instance(tmp_path) as (client, provider):
        setup_admin(client)
        response = sign_in(client, provider, person(sub="admin-sso", email="other@example.com"), link="1")
        assert response.headers["location"] == "/settings/security?linked=1"
        assert client.get("/api/v1/me").json()["oidc_linked"] is True
        assert client.delete("/api/v1/me/oidc").status_code == 204
        assert client.get("/api/v1/me").json()["oidc_linked"] is False


def test_an_identity_links_to_one_account_only(tmp_path: Path) -> None:
    with instance(tmp_path, oidc_auto_provision=True) as (client, provider):
        setup_admin(client)
        admin_cookies = dict(client.cookies)
        client.cookies.clear()
        sign_in(client, provider, person())
        client.cookies.clear()
        client.cookies.update(admin_cookies)
        response = sign_in(client, provider, person(), link="1")
        assert response.headers["location"] == "/settings/security?error=oidc_taken"


def test_unlinking_the_only_way_to_sign_in_is_refused(tmp_path: Path) -> None:
    with instance(tmp_path, oidc_auto_provision=True) as (client, provider):
        setup_admin(client)
        client.cookies.clear()
        sign_in(client, provider, person())
        refused = client.delete("/api/v1/me/oidc")
        assert (refused.status_code, refused.json()["code"]) == (409, "last_login_method")


def test_oidc_endpoints_are_absent_when_not_configured(admin: TestClient) -> None:
    assert admin.get("/api/v1/auth/oidc/login", follow_redirects=False).status_code == 404
    assert admin.get("/api/v1/config").json()["oidc_enabled"] is False
