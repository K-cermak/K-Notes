from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app import cli
from app.config import Settings
from tests.conftest import ADMIN, token_of, user_id


def test_reset_password_prints_a_working_link(
    admin: TestClient,
    settings: Settings,
    new_client: Callable[[], TestClient],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["reset-password", ADMIN["email"].upper()], settings) == 0
    url = capsys.readouterr().out.strip().splitlines()[-1]
    assert url.startswith("http://testserver/reset/")
    browser = new_client()
    response = browser.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": token_of(url), "password": "recovered-password"},
    )
    assert response.status_code == 200


def test_make_admin(
    admin: TestClient,
    settings: Settings,
    make_user: Callable[..., TestClient],
    capsys: pytest.CaptureFixture[str],
) -> None:
    user = make_user()
    assert cli.main(["make-admin", "user@example.com"], settings) == 0
    assert user.get("/api/v1/me").json()["is_admin"] is True
    assert "is now an admin" in capsys.readouterr().out


def test_disable_totp(admin: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["disable-totp", ADMIN["email"]], settings) == 0
    assert admin.get("/api/v1/me").json()["totp_enabled"] is False
    assert user_id(admin)


def test_unknown_email_fails(
    admin: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["make-admin", "nobody@example.com"], settings) == 1
    assert "No account" in capsys.readouterr().err


def test_requires_configuration(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    assert cli.main(["make-admin", "a@example.com"]) == 2
    assert "APP_BASE_URL" in capsys.readouterr().err
