from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pyotp.totp import TOTP

from app.db import Database
from app.models import User
from tests.conftest import ADMIN, PASSWORD, FakeClock

STEP_MS = 30_000


def code_at(secret: str, now_ms: int) -> str:
    return TOTP(secret).at(now_ms // 1000)


def enrol(client: TestClient, clock: FakeClock) -> tuple[str, list[str]]:
    setup = client.post("/api/v1/me/totp/setup")
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    enabled = client.post("/api/v1/me/totp/enable", json={"code": code_at(secret, clock.now)})
    assert enabled.status_code == 200, enabled.text
    return secret, enabled.json()["codes"]


def password_step(client: TestClient, email: str = ADMIN["email"], password: str = ADMIN["password"]) -> Any:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def test_enrolment_needs_a_working_code(admin: TestClient, fake_clock: FakeClock) -> None:
    setup = admin.post("/api/v1/me/totp/setup").json()
    assert setup["uri"].startswith("otpauth://totp/")
    assert "admin%40example.com" in setup["uri"]
    wrong = admin.post("/api/v1/me/totp/enable", json={"code": "000000"})
    assert (wrong.status_code, wrong.json()["code"]) == (422, "invalid_code")
    assert admin.get("/api/v1/me").json()["totp_enabled"] is False

    enabled = admin.post("/api/v1/me/totp/enable", json={"code": code_at(setup["secret"], fake_clock.now)})
    codes = enabled.json()["codes"]
    assert len(codes) == 10
    assert len(set(codes)) == 10
    assert admin.get("/api/v1/me").json()["totp_enabled"] is True
    assert admin.get("/api/v1/me/totp").json() == {"enabled": True, "recovery_codes_left": 10}
    assert admin.post("/api/v1/me/totp/setup").status_code == 409


def test_the_secret_is_encrypted_at_rest(app: FastAPI, admin: TestClient, fake_clock: FakeClock) -> None:
    secret, _ = enrol(admin, fake_clock)
    db: Database = app.state.db
    with db.reader() as session:
        stored = session.query(User).one().totp_secret
    assert stored is not None
    assert secret not in stored


def test_login_takes_two_steps(
    admin: TestClient, new_client: Callable[[], TestClient], fake_clock: FakeClock
) -> None:
    secret, _ = enrol(admin, fake_clock)
    browser = new_client()
    challenge = password_step(browser)
    assert challenge["totp_required"] is True
    assert "session" not in browser.cookies
    assert browser.get("/api/v1/me").status_code == 401

    # The code used for enrolment cannot be used again; the next one can.
    replay = {"pending_token": challenge["pending_token"], "code": code_at(secret, fake_clock.now)}
    assert browser.post("/api/v1/auth/login/totp", json=replay).status_code == 401
    fake_clock.advance(STEP_MS)
    code = code_at(secret, fake_clock.now)
    signed_in = browser.post(
        "/api/v1/auth/login/totp", json={"pending_token": challenge["pending_token"], "code": code}
    )
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["email"] == ADMIN["email"]
    assert browser.get("/api/v1/me").status_code == 200

    # A code is good for one sign-in only, even within its 30 seconds.
    other = new_client()
    again = {"pending_token": password_step(other)["pending_token"], "code": code}
    assert other.post("/api/v1/auth/login/totp", json=again).status_code == 401


def test_codes_from_the_neighbouring_steps_are_accepted(
    admin: TestClient, new_client: Callable[[], TestClient], fake_clock: FakeClock
) -> None:
    secret, _ = enrol(admin, fake_clock)
    fake_clock.advance(10 * STEP_MS)
    for offset, accepted in ((-2 * STEP_MS, False), (-STEP_MS, True), (STEP_MS, True)):
        browser = new_client()
        body = {
            "pending_token": password_step(browser)["pending_token"],
            "code": code_at(secret, fake_clock.now + offset),
        }
        status = browser.post("/api/v1/auth/login/totp", json=body).status_code
        assert (status == 200) is accepted, offset


def test_recovery_codes_work_once(
    admin: TestClient, new_client: Callable[[], TestClient], fake_clock: FakeClock
) -> None:
    _, codes = enrol(admin, fake_clock)
    browser = new_client()
    body = {"pending_token": password_step(browser)["pending_token"], "code": codes[0].upper()}
    assert browser.post("/api/v1/auth/login/totp", json=body).status_code == 200
    assert browser.get("/api/v1/me/totp").json()["recovery_codes_left"] == 9

    other = new_client()
    body = {"pending_token": password_step(other)["pending_token"], "code": codes[0]}
    assert other.post("/api/v1/auth/login/totp", json=body).status_code == 401


def test_new_recovery_codes_replace_the_old_ones(
    admin: TestClient, new_client: Callable[[], TestClient], fake_clock: FakeClock
) -> None:
    secret, old = enrol(admin, fake_clock)
    fake_clock.advance(STEP_MS)
    response = admin.post("/api/v1/me/totp/recovery-codes", json={"code": code_at(secret, fake_clock.now)})
    assert response.status_code == 200
    browser = new_client()
    body = {"pending_token": password_step(browser)["pending_token"], "code": old[1]}
    assert browser.post("/api/v1/auth/login/totp", json=body).status_code == 401


def test_the_pending_token_expires_and_cannot_be_forged(
    admin: TestClient, new_client: Callable[[], TestClient], fake_clock: FakeClock
) -> None:
    secret, _ = enrol(admin, fake_clock)
    browser = new_client()
    token = password_step(browser)["pending_token"]
    fake_clock.advance(6 * 60_000)
    body = {"pending_token": token, "code": code_at(secret, fake_clock.now)}
    assert browser.post("/api/v1/auth/login/totp", json=body).status_code == 401

    user_id, _, rest = password_step(browser)["pending_token"].partition(".")
    expires, _, signature = rest.partition(".")
    forged = f"{user_id}.{int(expires) + 3_600_000}.{signature}"
    body = {"pending_token": forged, "code": code_at(secret, fake_clock.now)}
    assert browser.post("/api/v1/auth/login/totp", json=body).status_code == 401


def test_wrong_codes_are_throttled(
    admin: TestClient, new_client: Callable[[], TestClient], fake_clock: FakeClock
) -> None:
    enrol(admin, fake_clock)
    browser = new_client()
    token = password_step(browser)["pending_token"]
    statuses = [
        browser.post("/api/v1/auth/login/totp", json={"pending_token": token, "code": "000000"}).status_code
        for _ in range(7)
    ]
    assert statuses[:5] == [401] * 5
    assert 429 in statuses[5:]


def test_turning_totp_off_needs_the_password_and_a_code(
    admin: TestClient, new_client: Callable[[], TestClient], fake_clock: FakeClock
) -> None:
    secret, _ = enrol(admin, fake_clock)
    fake_clock.advance(STEP_MS)
    code = code_at(secret, fake_clock.now)
    wrong_password = admin.post("/api/v1/me/totp/disable", json={"password": "nope-nope-nope", "code": code})
    assert wrong_password.json()["code"] == "wrong_password"
    wrong_code = admin.post("/api/v1/me/totp/disable", json={"password": ADMIN["password"], "code": "123456"})
    assert wrong_code.json()["code"] == "invalid_code"
    done = admin.post("/api/v1/me/totp/disable", json={"password": ADMIN["password"], "code": code})
    assert done.status_code == 204
    assert (
        "session"
        in new_client()
        .post("/api/v1/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]})
        .cookies
    )


def test_an_admin_can_reset_a_users_totp(
    admin: TestClient,
    make_user: Callable[..., TestClient],
    new_client: Callable[[], TestClient],
    fake_clock: FakeClock,
) -> None:
    user = make_user("b@example.com")
    enrol(user, fake_clock)
    user_id = user.get("/api/v1/me").json()["id"]
    assert user.delete(f"/api/v1/admin/users/{user_id}/totp").status_code == 403
    assert admin.delete(f"/api/v1/admin/users/{user_id}/totp").status_code == 204
    me = password_step(new_client(), "b@example.com", PASSWORD)
    assert me["email"] == "b@example.com"
    assert admin.delete("/api/v1/admin/users/unknown/totp").status_code == 404
