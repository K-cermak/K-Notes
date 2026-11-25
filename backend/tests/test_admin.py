import re
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import Database
from app.errors import ConflictError
from app.schemas.admin import AdminUserUpdate
from app.services import admin as admin_service
from app.services.clock import DAY_MS
from tests.conftest import ADMIN, PASSWORD, FakeClock, invite_url, token_of, user_id


def _admin_routes(app: FastAPI) -> list[tuple[str, str]]:
    return [
        (method.upper(), re.sub(r"\{\w+\}", "x", path))
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/v1/admin")
        for method in operations
    ]


def test_non_admin_cannot_reach_admin_endpoints(
    app: FastAPI, admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    user = make_user()
    routes = _admin_routes(app)
    assert len(routes) >= 9
    for method, path in routes:
        response = user.request(method, path, json={})
        assert response.status_code == 403, (method, path)
        assert response.json()["code"] == "not_admin"


def test_admin_endpoints_need_a_session(app: FastAPI, client: TestClient) -> None:
    for method, path in _admin_routes(app):
        assert client.request(method, path, json={}).status_code == 401, (method, path)


def test_invite_link_works_once(admin: TestClient, new_client: Callable[[], TestClient]) -> None:
    token = token_of(invite_url(admin))
    assert new_client().post("/api/v1/auth/invite/check", json={"token": token}).json() == {"email": None}
    body = {"token": token, "email": "friend@example.com", "display_name": "Friend", "password": PASSWORD}
    friend = new_client()
    assert friend.post("/api/v1/auth/invite/accept", json=body).status_code == 201
    assert friend.get("/api/v1/me").json()["email"] == "friend@example.com"
    again = new_client().post("/api/v1/auth/invite/accept", json={**body, "email": "other@example.com"})
    assert again.status_code == 404
    assert again.json()["code"] == "invalid_link"
    assert new_client().post("/api/v1/auth/invite/check", json={"token": token}).status_code == 404


def test_invite_link_expires_after_seven_days(
    admin: TestClient, new_client: Callable[[], TestClient], fake_clock: FakeClock
) -> None:
    token = token_of(invite_url(admin))
    fake_clock.advance(7 * DAY_MS + 1)
    body = {"token": token, "email": "late@example.com", "display_name": "Late", "password": PASSWORD}
    assert new_client().post("/api/v1/auth/invite/accept", json=body).json()["code"] == "invalid_link"


def test_invite_with_email_fixes_the_address(admin: TestClient, new_client: Callable[[], TestClient]) -> None:
    token = token_of(invite_url(admin, "Fixed@Example.com"))
    assert new_client().post("/api/v1/auth/invite/check", json={"token": token}).json() == {
        "email": "fixed@example.com"
    }
    body = {"token": token, "email": "other@example.com", "display_name": "Fixed", "password": PASSWORD}
    invited = new_client()
    invited.post("/api/v1/auth/invite/accept", json=body)
    assert invited.get("/api/v1/me").json()["email"] == "fixed@example.com"


def test_invite_for_existing_email_is_refused(admin: TestClient) -> None:
    response = admin.post("/api/v1/admin/invites", json={"email": ADMIN["email"]})
    assert response.json()["code"] == "email_taken"


def test_pending_invites_can_be_listed_and_revoked(
    admin: TestClient, new_client: Callable[[], TestClient]
) -> None:
    token = token_of(invite_url(admin, "pending@example.com"))
    pending = admin.get("/api/v1/admin/invites").json()
    assert [i["email"] for i in pending] == ["pending@example.com"]
    assert "token" not in pending[0]
    assert admin.delete(f"/api/v1/admin/invites/{pending[0]['id']}").status_code == 204
    assert new_client().post("/api/v1/auth/invite/check", json={"token": token}).status_code == 404
    assert admin.get("/api/v1/admin/invites").json() == []


def test_reset_link_works_once_and_signs_out_everywhere(
    admin: TestClient, make_user: Callable[..., TestClient], new_client: Callable[[], TestClient]
) -> None:
    user = make_user()
    link = admin.post(f"/api/v1/admin/users/{user_id(user)}/reset-link").json()
    token = token_of(link["url"])
    assert "/reset/" in link["url"]
    browser = new_client()
    assert browser.post("/api/v1/auth/password-reset/check", json={"token": token}).json() == {
        "email": "user@example.com"
    }
    response = browser.post(
        "/api/v1/auth/password-reset/complete", json={"token": token, "password": "brand-new-password"}
    )
    assert response.status_code == 200
    assert browser.get("/api/v1/me").status_code == 200
    assert user.get("/api/v1/me").status_code == 401
    reuse = new_client().post(
        "/api/v1/auth/password-reset/complete", json={"token": token, "password": "another-password"}
    )
    assert reuse.json()["code"] == "invalid_link"
    login = new_client().post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": "brand-new-password"}
    )
    assert login.status_code == 200


def test_reset_link_expires_after_a_day(
    admin: TestClient, make_user: Callable[..., TestClient], fake_clock: FakeClock
) -> None:
    user = make_user()
    token = token_of(admin.post(f"/api/v1/admin/users/{user_id(user)}/reset-link").json()["url"])
    fake_clock.advance(DAY_MS + 1)
    response = admin.post("/api/v1/auth/password-reset/check", json={"token": token})
    assert response.json()["code"] == "invalid_link"


def test_only_the_newest_reset_link_works(admin: TestClient, make_user: Callable[..., TestClient]) -> None:
    uid = user_id(make_user())
    first = token_of(admin.post(f"/api/v1/admin/users/{uid}/reset-link").json()["url"])
    second = token_of(admin.post(f"/api/v1/admin/users/{uid}/reset-link").json()["url"])
    assert admin.post("/api/v1/auth/password-reset/check", json={"token": first}).status_code == 404
    assert admin.post("/api/v1/auth/password-reset/check", json={"token": second}).status_code == 200


def test_invite_and_reset_tokens_are_not_interchangeable(
    admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    invite = token_of(invite_url(admin))
    reset = token_of(admin.post(f"/api/v1/admin/users/{user_id(make_user())}/reset-link").json()["url"])
    assert admin.post("/api/v1/auth/password-reset/check", json={"token": invite}).status_code == 404
    assert admin.post("/api/v1/auth/invite/check", json={"token": reset}).status_code == 404


def test_deactivated_user_is_signed_out_at_once_and_cannot_log_in(
    admin: TestClient, make_user: Callable[..., TestClient], new_client: Callable[[], TestClient]
) -> None:
    user = make_user()
    uid = user_id(user)
    response = admin.patch(f"/api/v1/admin/users/{uid}", json={"is_active": False})
    assert response.json()["is_active"] is False
    assert user.get("/api/v1/me").status_code == 401
    login = new_client().post("/api/v1/auth/login", json={"email": "user@example.com", "password": PASSWORD})
    assert login.status_code == 403
    assert login.json()["code"] == "account_disabled"
    reset = token_of(admin.post(f"/api/v1/admin/users/{uid}/reset-link").json()["url"])
    via_reset = new_client().post(
        "/api/v1/auth/password-reset/complete", json={"token": reset, "password": "brand-new-password"}
    )
    assert via_reset.json()["code"] == "account_disabled"

    admin.patch(f"/api/v1/admin/users/{uid}", json={"is_active": True})
    login = new_client().post("/api/v1/auth/login", json={"email": "user@example.com", "password": PASSWORD})
    assert login.status_code == 200


def test_admin_rights_take_effect_immediately(
    admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    user = make_user()
    uid = user_id(user)
    assert user.get("/api/v1/admin/users").status_code == 403
    admin.patch(f"/api/v1/admin/users/{uid}", json={"is_admin": True})
    assert user.get("/api/v1/admin/users").status_code == 200
    admin.patch(f"/api/v1/admin/users/{uid}", json={"is_admin": False})
    assert user.get("/api/v1/admin/users").status_code == 403


def test_admins_cannot_demote_deactivate_or_delete_themselves(admin: TestClient) -> None:
    me = user_id(admin)
    for change in ({"is_admin": False}, {"is_active": False}):
        response = admin.patch(f"/api/v1/admin/users/{me}", json=change)
        assert response.status_code == 409
        assert response.json()["code"] == "self_change"
    assert admin.delete(f"/api/v1/admin/users/{me}").json()["code"] == "self_change"
    assert admin.get("/api/v1/me").json()["is_admin"] is True


def test_another_admin_can_demote_while_one_remains(
    admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    second = make_user("second@example.com")
    admin.patch(f"/api/v1/admin/users/{user_id(second)}", json={"is_admin": True})
    response = second.patch(f"/api/v1/admin/users/{user_id(admin)}", json={"is_admin": False})
    assert response.status_code == 200
    assert admin.get("/api/v1/admin/users").status_code == 403


def test_last_active_admin_cannot_be_removed(app: FastAPI, admin: TestClient) -> None:
    # Through the API the self-change guard fires first, so this exercises the service as the CLI uses it.
    db: Database = app.state.db
    uid = user_id(admin)
    with db.writer() as session:
        for change in (AdminUserUpdate(is_admin=False), AdminUserUpdate(is_active=False)):
            with pytest.raises(ConflictError) as error:
                admin_service.update_user(session, None, uid, change)
            assert error.value.code == "last_admin"
        with pytest.raises(ConflictError):
            admin_service.delete_user(session, None, uid)


def test_inactive_admins_do_not_count_as_the_remaining_admin(
    app: FastAPI, admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    second = user_id(make_user("second@example.com"))
    admin.patch(f"/api/v1/admin/users/{second}", json={"is_admin": True})
    admin.patch(f"/api/v1/admin/users/{second}", json={"is_active": False})
    db: Database = app.state.db
    with db.writer() as session, pytest.raises(ConflictError):
        admin_service.update_user(session, None, user_id(admin), AdminUserUpdate(is_admin=False))


def test_delete_user_removes_their_account(
    admin: TestClient, make_user: Callable[..., TestClient], new_client: Callable[[], TestClient]
) -> None:
    user = make_user()
    uid = user_id(user)
    assert admin.delete(f"/api/v1/admin/users/{uid}").status_code == 204
    assert user.get("/api/v1/me").status_code == 401
    assert [u["email"] for u in admin.get("/api/v1/admin/users").json()] == [ADMIN["email"]]
    login = new_client().post("/api/v1/auth/login", json={"email": "user@example.com", "password": PASSWORD})
    assert login.status_code == 401
    assert admin.delete(f"/api/v1/admin/users/{uid}").status_code == 404


def test_admin_deleting_a_user_keeps_their_invites_valid(
    admin: TestClient, make_user: Callable[..., TestClient], new_client: Callable[[], TestClient]
) -> None:
    second = make_user("second@example.com")
    admin.patch(f"/api/v1/admin/users/{user_id(second)}", json={"is_admin": True})
    token = token_of(invite_url(second))
    admin.delete(f"/api/v1/admin/users/{user_id(second)}")
    assert new_client().post("/api/v1/auth/invite/check", json={"token": token}).status_code == 200


def test_user_list_and_status(admin: TestClient, make_user: Callable[..., TestClient]) -> None:
    make_user()
    users = admin.get("/api/v1/admin/users").json()
    assert [(u["email"], u["is_admin"]) for u in users] == [
        (ADMIN["email"], True),
        ("user@example.com", False),
    ]
    assert all(u["last_active_at"] for u in users)
    status = admin.get("/api/v1/admin/status").json()
    assert status["user_count"] == 2
    assert status["oidc_enabled"] is False


def test_unknown_user_returns_404(admin: TestClient) -> None:
    assert admin.patch("/api/v1/admin/users/nope", json={"is_active": False}).status_code == 404
    assert admin.post("/api/v1/admin/users/nope/reset-link").status_code == 404


def test_instance_limits_default_update_and_validation(admin: TestClient) -> None:
    def limits(settings: dict[str, Any]) -> dict[str, Any]:
        return {key: settings[key] for key in ("trash_retention_days", "max_image_mb", "session_days")}

    assert limits(admin.get("/api/v1/admin/settings").json()) == {
        "trash_retention_days": 7,
        "max_image_mb": 10,
        "session_days": 180,
    }
    changed = {"trash_retention_days": 0, "max_image_mb": 25, "session_days": 30}
    assert limits(admin.patch("/api/v1/admin/settings", json=changed).json()) == changed
    # A partial update leaves the others as they are.
    after = admin.patch("/api/v1/admin/settings", json={"registration_enabled": True}).json()
    assert limits(after) == changed

    config = admin.get("/api/v1/config").json()
    assert (config["trash_retention_days"], config["max_image_mb"]) == (0, 25)

    for invalid in (
        {"trash_retention_days": -1},
        {"trash_retention_days": 3651},
        {"max_image_mb": 0},
        {"max_image_mb": 101},
        {"session_days": 0},
        {"session_days": 3651},
    ):
        assert admin.patch("/api/v1/admin/settings", json=invalid).status_code == 422, invalid
