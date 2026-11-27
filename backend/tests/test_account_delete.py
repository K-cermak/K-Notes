from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import Database
from app.models import Note, User
from tests.conftest import ADMIN, PASSWORD, user_id


def delete_me(client: TestClient, **body: Any) -> Any:
    return client.request("DELETE", "/api/v1/me", json=body)


def notes_of(app: FastAPI, uid: str) -> int:
    database: Database = app.state.db
    with database.reader() as db:
        return db.scalar(select(func.count()).select_from(Note).where(Note.user_id == uid)) or 0


def test_a_user_deletes_their_account_with_their_notes(
    app: FastAPI,
    admin: TestClient,
    make_user: Callable[..., TestClient],
    new_client: Callable[[], TestClient],
) -> None:
    user = make_user()
    uid = user_id(user)
    assert user.post("/api/v1/notes", json={"title": "Mine"}).status_code == 201
    admin.post("/api/v1/notes", json={"title": "The admin's"})

    response = delete_me(user, password=PASSWORD)
    assert response.status_code == 204
    assert "session=" in response.headers["set-cookie"]
    assert user.get("/api/v1/me").status_code == 401
    assert notes_of(app, uid) == 0
    assert notes_of(app, user_id(admin)) == 1
    assert [u["email"] for u in admin.get("/api/v1/admin/users").json()] == [ADMIN["email"]]
    login = new_client().post("/api/v1/auth/login", json={"email": "user@example.com", "password": PASSWORD})
    assert login.status_code == 401


def test_a_wrong_password_keeps_the_account(make_user: Callable[..., TestClient]) -> None:
    user = make_user()
    for body in ({"password": "not-the-password"}, {}, {"email": "user@example.com"}):
        response = delete_me(user, **body)
        assert response.status_code == 422
        assert response.json()["code"] == "wrong_password"
    assert user.get("/api/v1/me").status_code == 200


def test_a_user_only_deletes_their_own_account(
    admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    first = make_user("first@example.com")
    second = make_user("second@example.com")
    assert delete_me(second, password=PASSWORD).status_code == 204
    assert first.get("/api/v1/me").status_code == 200
    assert admin.get("/api/v1/me").status_code == 200


def test_the_last_active_admin_cannot_delete_their_account(
    admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    response = delete_me(admin, password=ADMIN["password"])
    assert response.status_code == 409
    assert response.json()["code"] == "last_admin"
    assert admin.get("/api/v1/me").status_code == 200

    second = make_user("second@example.com")
    admin.patch(f"/api/v1/admin/users/{user_id(second)}", json={"is_admin": True})
    assert delete_me(admin, password=ADMIN["password"]).status_code == 204
    assert second.get("/api/v1/admin/users").status_code == 200


def test_an_account_without_a_password_confirms_with_its_email(
    app: FastAPI, make_user: Callable[..., TestClient]
) -> None:
    user = make_user()
    database: Database = app.state.db
    with database.writer() as db:
        account = db.get(User, user_id(user))
        assert account is not None
        account.password_hash = None
        account.oidc_issuer, account.oidc_subject = "https://id.example.com", "u-1"
        db.commit()

    response = delete_me(user, email="someone@example.com")
    assert response.status_code == 422
    assert response.json()["code"] == "wrong_email"
    assert delete_me(user, email=" User@Example.com ").status_code == 204
    assert user.get("/api/v1/me").status_code == 401


def test_an_api_token_cannot_delete_the_account(app: FastAPI, admin: TestClient) -> None:
    token = admin.post("/api/v1/me/tokens", json={"name": "Script", "scope": "write"}).json()["token"]
    script = TestClient(app)
    script.headers["Authorization"] = f"Bearer {token}"
    response = delete_me(script, password=ADMIN["password"])
    assert response.status_code == 403
    assert admin.get("/api/v1/me").status_code == 200
