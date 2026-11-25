from collections.abc import Callable

from fastapi.testclient import TestClient

from app.services.clock import DAY_MS
from tests.conftest import ADMIN, PASSWORD, FakeClock, setup_admin


def test_setup_creates_the_first_admin_and_signs_in(client: TestClient) -> None:
    assert client.get("/api/v1/config").json()["setup_required"] is True
    me = setup_admin(client)
    assert me["email"] == ADMIN["email"]
    assert me["is_admin"] is True
    assert client.get("/api/v1/me").json()["id"] == me["id"]
    assert client.get("/api/v1/config").json()["setup_required"] is False


def test_setup_works_only_once(admin: TestClient, new_client: Callable[[], TestClient]) -> None:
    other = {**ADMIN, "email": "intruder@example.com"}
    response = new_client().post("/api/v1/auth/setup", json=other)
    assert response.status_code == 409
    assert response.json()["code"] == "setup_done"


def test_setup_validates_input(client: TestClient) -> None:
    short = client.post("/api/v1/auth/setup", json={**ADMIN, "password": "short"})
    assert short.json()["code"] == "password_too_short"
    bad_email = client.post("/api/v1/auth/setup", json={**ADMIN, "email": "not-an-email"})
    assert bad_email.json()["code"] == "invalid_email"
    no_name = client.post("/api/v1/auth/setup", json={**ADMIN, "display_name": "  "})
    assert no_name.json()["code"] == "display_name_required"
    assert client.get("/api/v1/config").json()["setup_required"] is True


def test_session_cookie_attributes(client: TestClient) -> None:
    response = client.post("/api/v1/auth/setup", json=ADMIN)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert "secure" not in cookie  # base URL is http in tests


def test_login_and_logout(admin: TestClient, new_client: Callable[[], TestClient]) -> None:
    browser = new_client()
    assert browser.get("/api/v1/me").status_code == 401
    response = browser.post(
        "/api/v1/auth/login", json={"email": " Admin@Example.com ", "password": ADMIN["password"]}
    )
    assert response.status_code == 200
    assert browser.get("/api/v1/me").status_code == 200
    assert browser.post("/api/v1/auth/logout").status_code == 204
    assert browser.get("/api/v1/me").status_code == 401


def test_logout_revokes_the_session_on_the_server(
    admin: TestClient, new_client: Callable[[], TestClient]
) -> None:
    token = admin.cookies["session"]
    admin.post("/api/v1/auth/logout")
    replay = new_client()
    replay.cookies.set("session", token)
    assert replay.get("/api/v1/me").status_code == 401


def test_login_failure_does_not_reveal_whether_the_account_exists(admin: TestClient) -> None:
    wrong_password = admin.post(
        "/api/v1/auth/login", json={"email": ADMIN["email"], "password": "wrong-password"}
    )
    unknown = admin.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x" * 12})
    assert wrong_password.status_code == unknown.status_code == 401
    assert wrong_password.json() == unknown.json()


def test_failed_logins_are_throttled(admin: TestClient) -> None:
    attempt = {"email": ADMIN["email"], "password": "wrong-password"}
    codes = [admin.post("/api/v1/auth/login", json=attempt).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5
    assert 429 in codes[5:]
    throttled = admin.post("/api/v1/auth/login", json={**attempt, "password": ADMIN["password"]})
    assert throttled.status_code == 429
    assert throttled.json()["code"] == "too_many_requests"
    assert int(throttled.headers["retry-after"]) >= 1


def test_expired_session_is_refused(admin: TestClient, fake_clock: FakeClock) -> None:
    fake_clock.advance(181 * DAY_MS)
    assert admin.get("/api/v1/me").status_code == 401


def test_session_length_is_set_by_an_admin(
    admin: TestClient, new_client: Callable[[], TestClient], fake_clock: FakeClock
) -> None:
    assert admin.patch("/api/v1/admin/settings", json={"session_days": 2}).status_code == 200
    browser = new_client()
    response = browser.post(
        "/api/v1/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]}
    )
    assert f"max-age={2 * DAY_MS // 1000}" in response.headers["set-cookie"].lower()
    fake_clock.advance(3 * DAY_MS)
    assert browser.get("/api/v1/me").status_code == 401


def test_session_slides_forward_on_use(admin: TestClient, fake_clock: FakeClock) -> None:
    fake_clock.advance(100 * DAY_MS)
    response = admin.get("/api/v1/me")
    assert response.status_code == 200
    assert "session=" in response.headers.get("set-cookie", "")
    fake_clock.advance(100 * DAY_MS)
    assert admin.get("/api/v1/me").status_code == 200


def test_a_write_after_an_idle_hour_slides_the_session_too(admin: TestClient, fake_clock: FakeClock) -> None:
    # The write request already holds the database write lock, so the sliding must not wait for it.
    fake_clock.advance(DAY_MS)
    assert admin.patch("/api/v1/me", json={"display_name": "Ada"}).status_code == 200
    assert "session" in admin.cookies


def test_registration_is_closed_by_default(client: TestClient, admin: TestClient) -> None:
    body = {"email": "new@example.com", "display_name": "New", "password": PASSWORD}
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 403
    assert response.json()["code"] == "registration_closed"


def test_registration_when_open(admin: TestClient, new_client: Callable[[], TestClient]) -> None:
    admin.patch("/api/v1/admin/settings", json={"registration_enabled": True})
    assert admin.get("/api/v1/config").json()["registration_open"] is True
    visitor = new_client()
    body = {"email": "new@example.com", "display_name": "New", "password": PASSWORD}
    assert visitor.post("/api/v1/auth/register", json=body).status_code == 201
    assert visitor.get("/api/v1/me").json()["is_admin"] is False
    taken = new_client().post("/api/v1/auth/register", json={**body, "email": "NEW@example.com"})
    assert taken.status_code == 409
    assert taken.json()["code"] == "email_taken"
