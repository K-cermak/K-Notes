from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.clock import DAY_MS
from tests.conftest import FakeClock, user_id
from tests.sync_helpers import Device


def create_token(client: TestClient, scope: str = "read", **extra: Any) -> dict[str, Any]:
    response = client.post("/api/v1/me/tokens", json={"name": "Script", "scope": scope, **extra})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def bearer(app: FastAPI, admin: TestClient) -> Callable[[str], TestClient]:
    """A client without cookies that sends the given token. Through admin, the app has started."""
    del admin

    def make(token: str) -> TestClient:
        client = TestClient(app)
        client.headers["Authorization"] = f"Bearer {token}"
        return client

    return make


def test_a_token_is_shown_once_and_listed_by_its_prefix(admin: TestClient) -> None:
    created = create_token(admin, "write", expires_in_days=30)
    assert created["token"].startswith("ntk_")
    assert created["prefix"] == created["token"][:12]
    listed = admin.get("/api/v1/me/tokens").json()
    assert [t["id"] for t in listed] == [created["id"]]
    assert "token" not in listed[0]
    assert listed[0]["scope"] == "write"
    assert listed[0]["expires_at"] is not None


def test_a_read_token_reads_notes_and_cannot_write(
    admin: TestClient, bearer: Callable[[str], TestClient]
) -> None:
    write = bearer(create_token(admin, "write")["token"])
    assert write.post("/api/v1/notes", json={"title": "From a script"}).status_code == 201
    read = bearer(create_token(admin, "read")["token"])
    listed = read.get("/api/v1/notes")
    assert listed.status_code == 200
    assert [n["title"] for n in listed.json()["notes"]] == ["From a script"]
    refused = read.post("/api/v1/notes", json={"title": "Not allowed"})
    assert (refused.status_code, refused.json()["code"]) == (403, "insufficient_scope")
    note_id = listed.json()["notes"][0]["id"]
    assert read.patch(f"/api/v1/notes/{note_id}", json={"title": "x"}).status_code == 403
    assert read.delete(f"/api/v1/notes/{note_id}").status_code == 403


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/me"),
        ("PATCH", "/api/v1/me"),
        ("POST", "/api/v1/me/password"),
        ("GET", "/api/v1/me/sessions"),
        ("GET", "/api/v1/me/tokens"),
        ("POST", "/api/v1/me/tokens"),
        ("POST", "/api/v1/me/totp/setup"),
        ("GET", "/api/v1/admin/users"),
        ("POST", "/api/v1/admin/invites"),
        ("GET", "/api/v1/sync/pull"),
        ("POST", "/api/v1/sync/push"),
        ("POST", "/api/v1/auth/logout"),
    ],
)
def test_no_token_reaches_account_security_or_admin_endpoints(
    admin: TestClient, bearer: Callable[[str], TestClient], method: str, path: str
) -> None:
    client = bearer(create_token(admin, "write")["token"])
    response = client.request(method, path, json={})
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "token_not_allowed"


def test_a_token_cannot_be_combined_with_a_session_cookie(admin: TestClient) -> None:
    # The admin client carries the session cookie; adding a token header must not open /me to it.
    admin.headers["Authorization"] = f"Bearer {create_token(admin)['token']}"
    try:
        assert admin.get("/api/v1/me").status_code == 403
    finally:
        del admin.headers["Authorization"]


def test_invalid_expired_and_revoked_tokens_are_refused(
    admin: TestClient, bearer: Callable[[str], TestClient], fake_clock: FakeClock
) -> None:
    assert bearer("ntk_not-a-real-token").get("/api/v1/notes").status_code == 401
    assert bearer("garbage").get("/api/v1/notes").status_code == 401

    expiring = create_token(admin, expires_in_days=1)
    revoked = create_token(admin)
    assert admin.delete(f"/api/v1/me/tokens/{revoked['id']}").status_code == 204
    assert bearer(revoked["token"]).get("/api/v1/notes").status_code == 401
    assert bearer(expiring["token"]).get("/api/v1/notes").status_code == 200
    fake_clock.advance(2 * DAY_MS)
    assert bearer(expiring["token"]).get("/api/v1/notes").status_code == 401
    assert [t["id"] for t in admin.get("/api/v1/me/tokens").json()] == [expiring["id"]]


def test_a_deactivated_users_tokens_stop_working(
    admin: TestClient, make_user: Callable[..., TestClient], bearer: Callable[[str], TestClient]
) -> None:
    user = make_user("b@example.com")
    token = create_token(user)["token"]
    assert bearer(token).get("/api/v1/notes").status_code == 200
    admin.patch(f"/api/v1/admin/users/{user_id(user)}", json={"is_active": False})
    assert bearer(token).get("/api/v1/notes").status_code == 401


def test_tokens_records_last_use(admin: TestClient, bearer: Callable[[str], TestClient]) -> None:
    created = create_token(admin)
    assert admin.get("/api/v1/me/tokens").json()[0]["last_used_at"] is None
    bearer(created["token"]).get("/api/v1/labels")
    assert admin.get("/api/v1/me/tokens").json()[0]["last_used_at"] is not None


def test_users_cannot_reach_each_others_tokens_or_notes(
    admin: TestClient, make_user: Callable[..., TestClient], bearer: Callable[[str], TestClient]
) -> None:
    owner_token = create_token(admin, "write")
    note = bearer(owner_token["token"]).post("/api/v1/notes", json={"title": "Mine"}).json()
    intruder = make_user("b@example.com")
    assert intruder.delete(f"/api/v1/me/tokens/{owner_token['id']}").status_code == 404
    other = bearer(create_token(intruder, "write")["token"])
    assert other.get("/api/v1/notes").json() == {"notes": [], "total": 0}
    assert other.get(f"/api/v1/notes/{note['id']}").status_code == 404
    assert other.patch(f"/api/v1/notes/{note['id']}", json={"title": "Hacked"}).status_code == 404
    assert other.delete(f"/api/v1/notes/{note['id']}").status_code == 404
    assert bearer(owner_token["token"]).get(f"/api/v1/notes/{note['id']}").json()["title"] == "Mine"


def test_rest_notes_round_trip(
    admin: TestClient, bearer: Callable[[str], TestClient], device: Device
) -> None:
    api = bearer(create_token(admin, "write")["token"])
    text = api.post(
        "/api/v1/notes",
        json={"title": "Plan", "text": "Line one\nLine two", "color": "mint", "labels": ["Work", "Home"]},
    ).json()
    assert text["text"] == "Line one\nLine two"
    assert text["labels"] == ["Home", "Work"]
    checklist = api.post(
        "/api/v1/notes", json={"title": "Shop", "items": ["Milk", "Bread"], "labels": ["home"]}
    ).json()
    assert [i["text"] for i in checklist["items"]] == ["Milk", "Bread"]
    assert checklist["labels"] == ["Home"]
    assert [label["name"] for label in api.get("/api/v1/labels").json()] == ["Home", "Work"]

    # New notes go to the top, as in the app.
    assert [n["title"] for n in api.get("/api/v1/notes").json()["notes"]] == ["Shop", "Plan"]
    assert [n["title"] for n in api.get("/api/v1/notes", params={"label": "work"}).json()["notes"]] == [
        "Plan"
    ]
    assert [n["title"] for n in api.get("/api/v1/notes", params={"q": "line TWO"}).json()["notes"]] == [
        "Plan"
    ]
    page = api.get("/api/v1/notes", params={"limit": 1, "offset": 1}).json()
    assert (page["total"], [n["title"] for n in page["notes"]]) == (2, ["Plan"])

    edited = api.patch(f"/api/v1/notes/{text['id']}", json={"text": "Changed", "pinned": True}).json()
    assert (edited["text"], edited["pinned"]) == ("Changed", True)
    assert api.patch(f"/api/v1/notes/{checklist['id']}", json={"text": "x"}).json()["code"] == "not_text_note"
    archived = api.patch(f"/api/v1/notes/{text['id']}", json={"archived": True}).json()
    assert (archived["archived"], archived["pinned"]) == (True, False)
    assert [n["title"] for n in api.get("/api/v1/notes").json()["notes"]] == ["Shop"]
    assert len(api.get("/api/v1/notes", params={"archived": True}).json()["notes"]) == 1

    assert api.delete(f"/api/v1/notes/{checklist['id']}").json()["trashed"] is True
    assert [n["title"] for n in api.get("/api/v1/notes", params={"trashed": True}).json()["notes"]] == [
        "Shop"
    ]

    # The app sees the same notes through sync.
    device.pull()
    assert {n["title"] for n in device.live("notes").values()} == {"Plan", "Shop"}


def test_rest_input_is_validated(admin: TestClient, bearer: Callable[[str], TestClient]) -> None:
    api = bearer(create_token(admin, "write")["token"])
    assert api.post("/api/v1/notes", json={"text": "a", "items": ["b"]}).status_code == 422
    assert api.post("/api/v1/notes", json={"color": "purple"}).status_code == 422
    assert api.post("/api/v1/notes", json={"labels": ["x" * 51]}).status_code == 422
    assert api.get("/api/v1/notes", params={"limit": 0}).status_code == 422
