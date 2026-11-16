from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import clock
from tests.sync_helpers import Device

ADMIN = {"email": "admin@example.com", "display_name": "Admin", "password": "admin-password"}
PASSWORD = "user-password"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(base_url="http://testserver", data_dir=tmp_path / "data")


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>index</title>")
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)")
    (dist / "sw.js").write_text("self")
    return dist


@pytest.fixture
def app(settings: Settings, static_dir: Path) -> FastAPI:
    return create_app(settings, static_dir=static_dir)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def new_client(app: FastAPI, client: TestClient) -> Callable[[], TestClient]:
    """Another browser: same server, its own cookie jar. Depends on client so the app has started."""
    return lambda: TestClient(app)


class FakeClock:
    def __init__(self) -> None:
        self.now = clock.now_ms()

    def __call__(self) -> int:
        return self.now

    def advance(self, ms: int) -> None:
        self.now += ms


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(clock, "now_ms", fake)
    return fake


def setup_admin(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/v1/auth/setup", json=ADMIN)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def admin(client: TestClient) -> TestClient:
    """The default client, signed in as the first admin."""
    setup_admin(client)
    return client


def invite_url(admin: TestClient, email: str | None = None) -> str:
    response = admin.post("/api/v1/admin/invites", json={"email": email})
    assert response.status_code == 201, response.text
    return response.json()["url"]


def token_of(url: str) -> str:
    return url.rsplit("/", 1)[1]


@pytest.fixture
def make_user(admin: TestClient, new_client: Callable[[], TestClient]) -> Callable[..., TestClient]:
    """Invite and sign up a user; returns their signed-in client."""

    def make(email: str = "user@example.com", display_name: str = "User") -> TestClient:
        user = new_client()
        response = user.post(
            "/api/v1/auth/invite/accept",
            json={
                "token": token_of(invite_url(admin)),
                "email": email,
                "display_name": display_name,
                "password": PASSWORD,
            },
        )
        assert response.status_code == 201, response.text
        return user

    return make


def user_id(client: TestClient) -> str:
    return client.get("/api/v1/me").json()["id"]


@pytest.fixture
def device(admin: TestClient) -> Device:
    return Device(admin)


@pytest.fixture
def second_device(admin: TestClient, new_client: Callable[[], TestClient]) -> Device:
    """The same user on another device, with its own session."""
    other = new_client()
    other.post("/api/v1/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]})
    return Device(other)
