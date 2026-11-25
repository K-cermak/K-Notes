"""The captcha on sign-in and registration, with the providers' verification endpoints faked."""

from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs

import altcha
import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import cli
from app.config import Settings
from app.services import captcha
from tests.conftest import ADMIN, PASSWORD, invite_url, token_of

LOGIN = {"email": ADMIN["email"], "password": ADMIN["password"]}
TURNSTILE = {"provider": "turnstile", "placement": "both", "site_key": "site-1", "secret_key": "secret-1"}


class FakeProvider:
    """Accepts "good-<secret>" tokens; any other secret than the known ones is rejected as invalid."""

    def __init__(self) -> None:
        self.secrets = {"secret-1", "secret-2"}
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.down = False

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        form = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        self.requests.append((str(request.url), form))
        if self.down:
            return httpx2.Response(503)
        if form["secret"] not in self.secrets:
            return httpx2.Response(200, json={"success": False, "error-codes": ["invalid-input-secret"]})
        ok = form["response"] == f"good-{form['secret']}"
        return httpx2.Response(
            200, json={"success": ok, "error-codes": [] if ok else ["invalid-input-response"]}
        )


@pytest.fixture
def provider(app: FastAPI, client: TestClient) -> FakeProvider:
    fake = FakeProvider()
    app.state.captcha.transport = httpx2.MockTransport(fake.handle)
    return fake


def enable(admin: TestClient, **overrides: Any) -> None:
    body = {**TURNSTILE, "token": f"good-{overrides.get('secret_key', TURNSTILE['secret_key'])}", **overrides}
    response = admin.put("/api/v1/admin/captcha", json=body)
    assert response.status_code == 200, response.text


def register(client: TestClient, **extra: Any) -> httpx2.Response:
    body = {"email": "new@example.com", "display_name": "New", "password": PASSWORD, **extra}
    return client.post("/api/v1/auth/register", json=body)


def test_off_by_default(admin: TestClient, new_client: Callable[[], TestClient]) -> None:
    assert admin.get("/api/v1/config").json()["captcha"] is None
    assert admin.get("/api/v1/admin/captcha").json() == {
        "provider": "none",
        "placement": "both",
        "site_key": "",
        "secret_key_set": False,
    }
    assert new_client().post("/api/v1/auth/login", json=LOGIN).status_code == 200


def test_new_keys_need_a_token_solved_with_them(admin: TestClient, provider: FakeProvider) -> None:
    missing = admin.put("/api/v1/admin/captcha", json=TURNSTILE)
    assert missing.status_code == 400
    assert missing.json()["code"] == "captcha_failed"
    wrong = admin.put("/api/v1/admin/captcha", json={**TURNSTILE, "token": "good-secret-2"})
    assert wrong.json()["code"] == "captcha_failed"
    assert admin.get("/api/v1/admin/captcha").json()["provider"] == "none"

    enable(admin)
    assert provider.requests[-1][0] == captcha.VERIFY_URLS["turnstile"]
    assert admin.get("/api/v1/admin/captcha").json() == {
        "provider": "turnstile",
        "placement": "both",
        "site_key": "site-1",
        "secret_key_set": True,
    }
    assert admin.get("/api/v1/config").json()["captcha"] == {
        "provider": "turnstile",
        "site_key": "site-1",
        "login": True,
        "registration": True,
    }


def test_a_rejected_secret_key_is_named(admin: TestClient, provider: FakeProvider) -> None:
    response = admin.put("/api/v1/admin/captcha", json={**TURNSTILE, "secret_key": "typo", "token": "x"})
    assert response.status_code == 422
    assert response.json()["code"] == "captcha_secret_invalid"


def test_keys_are_required_for_hosted_providers(admin: TestClient, provider: FakeProvider) -> None:
    no_site = admin.put("/api/v1/admin/captcha", json={**TURNSTILE, "site_key": " "})
    assert no_site.json()["code"] == "captcha_site_key_required"
    no_secret = admin.put("/api/v1/admin/captcha", json={**TURNSTILE, "secret_key": ""})
    assert no_secret.json()["code"] == "captcha_secret_key_required"


def test_placement_alone_changes_without_a_token_and_keeps_the_secret(
    admin: TestClient, provider: FakeProvider
) -> None:
    enable(admin)
    response = admin.put(
        "/api/v1/admin/captcha", json={**TURNSTILE, "placement": "registration", "secret_key": ""}
    )
    assert response.status_code == 200
    assert response.json()["secret_key_set"] is True
    # Another provider does not inherit the stored secret.
    other = admin.put("/api/v1/admin/captcha", json={**TURNSTILE, "provider": "hcaptcha", "secret_key": ""})
    assert other.json()["code"] == "captcha_secret_key_required"


def test_login_needs_a_solved_captcha(
    admin: TestClient, provider: FakeProvider, new_client: Callable[[], TestClient]
) -> None:
    enable(admin)
    browser = new_client()
    for token in (None, "bad"):
        response = browser.post("/api/v1/auth/login", json={**LOGIN, "captcha_token": token})
        assert response.status_code == 400
        assert response.json()["code"] == "captcha_failed"
    response = browser.post("/api/v1/auth/login", json={**LOGIN, "captcha_token": "good-secret-1"})
    assert response.status_code == 200
    url, form = provider.requests[-1]
    assert url == captcha.VERIFY_URLS["turnstile"]
    assert form == {"secret": "secret-1", "response": "good-secret-1", "remoteip": "testclient"}


def test_a_failed_captcha_does_not_count_as_a_wrong_password(
    admin: TestClient, provider: FakeProvider, new_client: Callable[[], TestClient]
) -> None:
    enable(admin)
    browser = new_client()
    for _ in range(10):
        browser.post("/api/v1/auth/login", json=LOGIN)
    response = browser.post("/api/v1/auth/login", json={**LOGIN, "captcha_token": "good-secret-1"})
    assert response.status_code == 200


def test_placement_decides_which_forms_ask(
    admin: TestClient, provider: FakeProvider, new_client: Callable[[], TestClient]
) -> None:
    admin.patch("/api/v1/admin/settings", json={"registration_enabled": True})
    enable(admin, placement="registration")
    assert new_client().post("/api/v1/auth/login", json=LOGIN).status_code == 200

    assert register(new_client()).json()["code"] == "captcha_failed"
    assert register(new_client(), captcha_token="good-secret-1").status_code == 201

    invite = {"token": token_of(invite_url(admin)), "email": "invited@example.com"}
    invite |= {"display_name": "Invited", "password": PASSWORD}
    refused = new_client().post("/api/v1/auth/invite/accept", json=invite)
    assert refused.json()["code"] == "captcha_failed"
    accepted = new_client().post(
        "/api/v1/auth/invite/accept", json={**invite, "captcha_token": "good-secret-1"}
    )
    assert accepted.status_code == 201

    enable(admin, placement="login")
    assert new_client().post("/api/v1/auth/login", json=LOGIN).json()["code"] == "captcha_failed"
    assert register(new_client(), email="other@example.com").status_code == 201


def test_hcaptcha_also_sends_the_site_key(
    admin: TestClient, provider: FakeProvider, new_client: Callable[[], TestClient]
) -> None:
    enable(admin, provider="hcaptcha", secret_key="secret-2")
    new_client().post("/api/v1/auth/login", json={**LOGIN, "captcha_token": "good-secret-2"})
    url, form = provider.requests[-1]
    assert url == captcha.VERIFY_URLS["hcaptcha"]
    assert form["sitekey"] == "site-1"


def test_an_unreachable_provider_refuses_rather_than_lets_through(
    admin: TestClient, provider: FakeProvider, new_client: Callable[[], TestClient]
) -> None:
    enable(admin, provider="recaptcha")
    provider.down = True
    response = new_client().post("/api/v1/auth/login", json={**LOGIN, "captcha_token": "good-secret-1"})
    assert response.status_code == 502
    assert response.json()["code"] == "captcha_unavailable"


def test_only_admins_see_or_change_the_captcha(
    admin: TestClient, provider: FakeProvider, make_user: Callable[..., TestClient]
) -> None:
    user = make_user()
    enable(admin)
    assert user.get("/api/v1/admin/captcha").json()["code"] == "not_admin"
    response = user.put("/api/v1/admin/captcha", json={"provider": "none", "placement": "both"})
    assert response.status_code == 403
    assert "secret" not in str(user.get("/api/v1/config").json())


@pytest.fixture
def quick_altcha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(captcha, "ALTCHA_COST", 10)
    monkeypatch.setattr(captcha, "ALTCHA_MAX_COUNTER", 20)


def solve(client: TestClient) -> str:
    response = client.get("/api/v1/auth/captcha/challenge")
    assert response.status_code == 200
    challenge = altcha.Challenge.from_dict(response.json())  # pyright: ignore[reportUnknownMemberType]
    solution = altcha.solve_challenge(challenge)  # pyright: ignore[reportUnknownMemberType]
    assert solution is not None
    return altcha.Payload(challenge, solution).to_base64()


def test_altcha_needs_no_keys_and_issues_its_own_challenges(
    admin: TestClient, quick_altcha: None, new_client: Callable[[], TestClient]
) -> None:
    assert admin.get("/api/v1/auth/captcha/challenge").status_code == 404
    response = admin.put("/api/v1/admin/captcha", json={"provider": "altcha", "placement": "login"})
    assert response.status_code == 200
    assert admin.get("/api/v1/config").json()["captcha"]["provider"] == "altcha"

    browser = new_client()
    payload = solve(browser)
    assert browser.post("/api/v1/auth/login", json={**LOGIN, "captcha_token": payload}).status_code == 200
    replayed = new_client().post("/api/v1/auth/login", json={**LOGIN, "captcha_token": payload})
    assert replayed.json()["code"] == "captcha_failed"


def test_altcha_refuses_forged_solutions(
    admin: TestClient, quick_altcha: None, new_client: Callable[[], TestClient]
) -> None:
    admin.put("/api/v1/admin/captcha", json={"provider": "altcha", "placement": "both"})
    forged = altcha.create_challenge("PBKDF2/SHA-256", 10, counter=3, hmac_secret="guess")  # pyright: ignore[reportUnknownMemberType]
    solution = altcha.solve_challenge(forged)  # pyright: ignore[reportUnknownMemberType]
    assert solution is not None
    for token in (altcha.Payload(forged, solution).to_base64(), "not base64!", ""):
        response = new_client().post("/api/v1/auth/login", json={**LOGIN, "captcha_token": token})
        assert response.json()["code"] == "captcha_failed", token


def test_cli_turns_the_captcha_off(
    admin: TestClient, provider: FakeProvider, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    enable(admin)
    assert cli.main(["disable-captcha"], settings) == 0
    assert "captcha is now off" in capsys.readouterr().out
    assert admin.get("/api/v1/config").json()["captcha"] is None


def test_the_captcha_frame_alone_allows_the_provider(client: TestClient) -> None:
    turnstile = client.get("/captcha.html?provider=turnstile").headers["content-security-policy"]
    assert "script-src 'self' https://challenges.cloudflare.com" in turnstile
    assert "frame-src 'self' https://challenges.cloudflare.com" in turnstile
    assert "frame-ancestors 'self'" in turnstile
    recaptcha = client.get("/captcha.html?provider=recaptcha").headers["content-security-policy"]
    assert "https://www.gstatic.com/recaptcha/" in recaptcha
    assert "cloudflare" not in recaptcha
    for path in ("/", "/login", "/captcha.html?provider=https://evil.test", "/other.html?provider=turnstile"):
        csp = client.get(path).headers["content-security-policy"]
        assert "https://" not in csp, path
        assert "frame-ancestors 'none'" in csp, path
