from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.conftest import ADMIN, PASSWORD


def test_profile_update(admin: TestClient) -> None:
    response = admin.patch(
        "/api/v1/me",
        json={
            "display_name": " Ada ",
            "locale": "cs",
            "theme": "dark",
            "default_view": "list",
            "time_format": "12h",
        },
    )
    assert response.status_code == 200
    me = admin.get("/api/v1/me").json()
    assert (me["display_name"], me["locale"], me["theme"], me["default_view"], me["time_format"]) == (
        "Ada",
        "cs",
        "dark",
        "list",
        "12h",
    )


def test_time_format_defaults_to_24_hours(admin: TestClient) -> None:
    assert admin.get("/api/v1/me").json()["time_format"] == "24h"


def test_profile_rejects_unknown_values(admin: TestClient) -> None:
    assert admin.patch("/api/v1/me", json={"theme": "sepia"}).status_code == 422
    assert admin.patch("/api/v1/me", json={"time_format": "36h"}).status_code == 422
    assert admin.patch("/api/v1/me", json={"locale": "<script>"}).status_code == 422


def test_change_password_revokes_other_sessions(
    admin: TestClient, new_client: Callable[[], TestClient]
) -> None:
    phone = new_client()
    phone.post("/api/v1/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]})
    response = admin.post(
        "/api/v1/me/password", json={"current_password": ADMIN["password"], "new_password": "new-password-1"}
    )
    assert response.status_code == 204
    assert admin.get("/api/v1/me").status_code == 200
    assert phone.get("/api/v1/me").status_code == 401
    old = new_client().post(
        "/api/v1/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]}
    )
    assert old.status_code == 401
    new = new_client().post(
        "/api/v1/auth/login", json={"email": ADMIN["email"], "password": "new-password-1"}
    )
    assert new.status_code == 200


def test_change_password_needs_the_current_one(admin: TestClient) -> None:
    response = admin.post(
        "/api/v1/me/password", json={"current_password": "wrong-password", "new_password": "new-password-1"}
    )
    assert response.json()["code"] == "wrong_password"
    short = admin.post(
        "/api/v1/me/password", json={"current_password": ADMIN["password"], "new_password": "x"}
    )
    assert short.json()["code"] == "password_too_short"


def test_list_and_revoke_sessions(admin: TestClient, new_client: Callable[[], TestClient]) -> None:
    phone = new_client()
    phone.post(
        "/api/v1/auth/login",
        json={"email": ADMIN["email"], "password": ADMIN["password"]},
        headers={"user-agent": "Phone"},
    )
    listed = admin.get("/api/v1/me/sessions").json()
    assert len(listed) == 2
    assert [s["current"] for s in listed].count(True) == 1
    other = next(s for s in listed if not s["current"])
    assert other["user_agent"] == "Phone"
    assert admin.delete(f"/api/v1/me/sessions/{other['id']}").status_code == 204
    assert phone.get("/api/v1/me").status_code == 401
    assert len(admin.get("/api/v1/me/sessions").json()) == 1


def test_revoke_all_other_sessions(admin: TestClient, new_client: Callable[[], TestClient]) -> None:
    for _ in range(2):
        new_client().post("/api/v1/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]})
    assert admin.delete("/api/v1/me/sessions").status_code == 204
    assert [s["current"] for s in admin.get("/api/v1/me/sessions").json()] == [True]


def test_user_cannot_see_or_revoke_another_users_session(
    admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    user = make_user()
    admin_session = admin.get("/api/v1/me/sessions").json()[0]["id"]
    assert all(s["id"] != admin_session for s in user.get("/api/v1/me/sessions").json())
    response = user.delete(f"/api/v1/me/sessions/{admin_session}")
    assert response.status_code == 404
    assert admin.get("/api/v1/me").status_code == 200


def test_account_endpoints_need_a_session(client: TestClient) -> None:
    for method, path in [
        ("GET", "/api/v1/me"),
        ("PATCH", "/api/v1/me"),
        ("POST", "/api/v1/me/password"),
        ("GET", "/api/v1/me/sessions"),
        ("DELETE", "/api/v1/me/sessions"),
        ("POST", "/api/v1/auth/logout"),
    ]:
        response = client.request(method, path, json={})
        assert response.status_code == 401, path
        assert response.json()["code"] == "unauthorized"


def test_password_is_never_returned(admin: TestClient, make_user: Callable[..., TestClient]) -> None:
    make_user()
    for path in ("/api/v1/me", "/api/v1/admin/users"):
        assert PASSWORD not in admin.get(path).text
        assert "password_hash" not in admin.get(path).text
