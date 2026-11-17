from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import user_id
from tests.sync_helpers import Device, doc, new_id, note_fields
from tests.test_blobs import attach, image_bytes, sha, upload


def storage(client: TestClient) -> dict[str, Any]:
    return client.get("/api/v1/me/storage").json()


def set_limit(admin: TestClient, user: TestClient, limit: Any) -> dict[str, Any]:
    response = admin.patch(f"/api/v1/admin/users/{user_id(user)}", json={"storage_limit": limit})
    assert response.status_code == 200, response.text
    return response.json()


def test_usage_counts_text_trash_and_each_image_once(make_user: Callable[..., TestClient]) -> None:
    user = make_user("b@example.com")
    device = Device(user)
    assert storage(user) == {"used_bytes": 0, "limit_bytes": None, "full": False}

    note_id, item_id = new_id(), new_id()
    device.sync(
        device.op("note", note_id, note_fields(title="Title", content=doc("Some text")), base_seq=0),
        device.op("checklist_item", item_id, {"note_id": note_id, "text": "Milk", "position": "a0"}),
    )
    text_only = storage(user)["used_bytes"]
    assert text_only > len("Title") + len("Some text") + len("Milk")

    data = image_bytes()
    assert upload(user, data).status_code == 204
    attach(device, sha(data))
    attach(device, sha(data))
    with_images = storage(user)["used_bytes"]
    assert with_images - text_only < 2 * len(data) + 2000
    assert with_images - text_only >= len(data)

    # The trash still counts; a purged note does not.
    device.sync(device.op("note", note_id, {"trashed_at": 1}))
    assert storage(user)["used_bytes"] >= with_images
    device.sync(device.op("note", note_id, kind="purge"))
    assert storage(user)["used_bytes"] < with_images


def test_limits_default_custom_unlimited_and_admins(
    admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    user = make_user("b@example.com")
    assert (
        admin.patch("/api/v1/admin/settings", json={"default_storage_limit_bytes": 5000}).status_code == 200
    )
    assert storage(user)["limit_bytes"] == 5000
    assert storage(admin)["limit_bytes"] is None

    assert set_limit(admin, user, 100)["storage_limit"] == 100
    assert storage(user) == {"used_bytes": 0, "limit_bytes": 100, "full": False}
    listed = set_limit(admin, user, "unlimited")
    assert (listed["storage_limit"], listed["storage_limit_bytes"]) == ("unlimited", None)
    assert set_limit(admin, user, "default")["storage_limit_bytes"] == 5000

    # Sent as null, the default becomes unlimited again.
    settings = admin.patch("/api/v1/admin/settings", json={"default_storage_limit_bytes": None}).json()
    assert settings["default_storage_limit_bytes"] is None
    assert storage(user)["limit_bytes"] is None
    assert (
        admin.patch("/api/v1/admin/settings", json={"registration_enabled": True}).json()[
            "default_storage_limit_bytes"
        ]
        is None
    )

    assert admin.patch(f"/api/v1/admin/users/{user_id(user)}", json={"storage_limit": -5}).status_code == 422
    assert (
        user.patch(f"/api/v1/admin/users/{user_id(user)}", json={"storage_limit": "unlimited"}).status_code
        == 403
    )


def test_over_the_limit_the_rest_api_refuses_new_notes_but_sync_accepts(
    app: Any, admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    user = make_user("b@example.com")
    device = Device(user)
    token = user.post("/api/v1/me/tokens", json={"name": "s", "scope": "write"}).json()["token"]
    api = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    set_limit(admin, user, 200)

    first = api.post("/api/v1/notes", json={"title": "Long", "text": "x" * 300})
    assert first.status_code == 201
    assert storage(user)["full"] is True
    refused = api.post("/api/v1/notes", json={"title": "More"})
    assert (refused.status_code, refused.json()["code"]) == (409, "storage_full")

    # Edits and syncing devices go on: an offline device could not have known.
    note_id = first.json()["id"]
    assert api.patch(f"/api/v1/notes/{note_id}", json={"text": "y" * 400}).status_code == 200
    assert device.sync(device.op("note", new_id(), note_fields(title="Offline"), base_seq=0)) == ["applied"]

    device.pull()
    for row_id in list(device.live("notes")):
        device.sync(device.op("note", row_id, kind="purge"))
    assert storage(user)["full"] is False
    assert api.post("/api/v1/notes", json={"title": "Again"}).status_code == 201


def test_admins_are_never_limited(admin: TestClient) -> None:
    admin.patch("/api/v1/admin/settings", json={"default_storage_limit_bytes": 0})
    assert storage(admin) == {"used_bytes": 0, "limit_bytes": None, "full": False}
