import asyncio
import threading
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import run_maintenance
from app.models import AppliedOp, AuthSession, Invite, Note
from app.services import maintenance, pull
from app.services.clock import DAY_MS
from app.services.events import EventHub
from tests.conftest import FakeClock, invite_url
from tests.sync_helpers import TABLES, Device, doc, new_id, note_fields

MINUTE = 60_000


def test_pull_needs_a_session(client: TestClient) -> None:
    assert client.get("/api/v1/sync/pull").status_code == 401
    assert client.post("/api/v1/sync/push", json={"device_id": "x", "ops": []}).status_code == 401
    assert client.get("/api/v1/sync/events").status_code == 401


def test_pull_is_windowed(device: Device, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull, "MAX_PULL_WINDOW", 3)
    ids = [new_id() for _ in range(7)]
    device.push(*[device.op("note", i, note_fields(title=str(n)), base_seq=0) for n, i in enumerate(ids)])
    pages: list[dict[str, Any]] = []
    since = 0
    while True:
        body = device.client.get("/api/v1/sync/pull", params={"since": since}).json()
        pages.append(body)
        since = body["seq"]
        if not body["has_more"]:
            break
    assert [len(p["changes"]["notes"]) for p in pages] == [3, 3, 1]
    assert [p["seq"] for p in pages] == [3, 6, 7]
    assert sorted(n["id"] for p in pages for n in p["changes"]["notes"]) == sorted(ids)
    empty = device.client.get("/api/v1/sync/pull", params={"since": 7}).json()
    assert empty == {"seq": 7, "has_more": False, "changes": {t: [] for t in TABLES}}


def test_pull_returns_each_row_once_at_its_latest_version(device: Device) -> None:
    note_id = new_id()
    device.push(
        device.op("note", note_id, note_fields(), base_seq=0),
        device.op("note", note_id, {"title": "v2"}, base_seq=0),
        device.op("note", note_id, {"title": "v3"}, base_seq=0),
    )
    body = device.client.get("/api/v1/sync/pull", params={"since": 0}).json()
    assert [n["title"] for n in body["changes"]["notes"]] == ["v3"]


def test_a_cursor_ahead_of_the_server_gets_the_current_counter(device: Device) -> None:
    device.push(device.op("note", new_id(), note_fields(), base_seq=0))
    body = device.client.get("/api/v1/sync/pull", params={"since": 500}).json()
    assert body["seq"] == 1
    assert body["has_more"] is False


def test_users_cannot_read_or_write_each_others_rows(
    device: Device, make_user: Callable[..., TestClient]
) -> None:
    note_id, label_id = new_id(), new_id()
    device.sync(
        device.op("note", note_id, note_fields(title="A's secret"), base_seq=0),
        device.op("label", label_id, {"name": "A's label"}),
    )
    intruder = Device(make_user("b@example.com"))
    intruder.pull()
    assert all(intruder.rows[t] == {} for t in TABLES)

    # B reusing A's IDs only ever reaches B's own rows.
    assert intruder.push(intruder.op("note", note_id, {"title": "Hacked"}, base_seq=99)) == [
        "rejected:missing_field"
    ]
    assert intruder.push(intruder.op("checklist_item", new_id(), {"note_id": note_id, "position": "a0"})) == [
        "gone"
    ]
    assert intruder.push(intruder.op("note", note_id, kind="purge")) == ["gone"]
    assert intruder.push(intruder.op("label", label_id, kind="purge")) == ["gone"]
    own = intruder.op("note", note_id, note_fields(title="B's own"), base_seq=0)
    assert intruder.sync(own) == ["applied"]
    assert intruder.push(intruder.op("note_label", f"{note_id}:{label_id}")) == ["gone"]

    device.pull()
    assert device.note(note_id)["title"] == "A's secret"
    assert intruder.note(note_id)["title"] == "B's own"
    assert len(device.rows["notes"]) == 1


def test_counters_are_per_user(device: Device, make_user: Callable[..., TestClient]) -> None:
    device.push(*[device.op("note", new_id(), note_fields(), base_seq=0) for _ in range(5)])
    other = Device(make_user("b@example.com"))
    assert other.push_raw(other.op("note", new_id(), note_fields(), base_seq=0))["seq"] == 1


def test_deleting_a_user_removes_their_notes(
    app: FastAPI, admin: TestClient, make_user: Callable[..., TestClient]
) -> None:
    user = make_user("b@example.com")
    device = Device(user)
    device.push(device.op("note", new_id(), note_fields(), base_seq=0))
    user_id = user.get("/api/v1/me").json()["id"]
    assert admin.delete(f"/api/v1/admin/users/{user_id}").status_code == 204
    db: Database = app.state.db
    with db.reader() as session:
        assert session.query(Note).count() == 0


def test_two_devices_converge_with_one_conflict_copy(
    device: Device, second_device: Device, fake_clock: FakeClock
) -> None:
    """A scripted day of offline editing on a laptop and a phone."""
    laptop, phone = device, second_device
    groceries, ideas, work, item_milk, item_eggs = (new_id() for _ in range(5))
    laptop.sync(
        laptop.op(
            "note", groceries, note_fields(type="checklist", title="Groceries", position="a0"), base_seq=0
        ),
        laptop.op("checklist_item", item_milk, {"note_id": groceries, "text": "Milk", "position": "a0"}),
        laptop.op("checklist_item", item_eggs, {"note_id": groceries, "text": "Eggs", "position": "a1"}),
        laptop.op("note", ideas, note_fields(title="Ideas", content=doc("first"), position="a1"), base_seq=0),
        laptop.op("label", work, {"name": "Work"}),
    )
    phone.pull()

    # Both go offline and edit.
    fake_clock.advance(MINUTE)
    laptop_ops = [
        laptop.op("checklist_item", item_milk, {"checked": True}),
        laptop.op("note", ideas, {"content": doc("laptop version")}),
        laptop.op("note_label", f"{ideas}:{work}"),
    ]
    fake_clock.advance(MINUTE)
    phone_ops = [
        phone.op("checklist_item", item_eggs, {"checked": True}),
        phone.op("note", ideas, {"content": doc("phone version"), "color": "mint"}),
        phone.op("note", groceries, {"pinned": True}),
    ]

    assert laptop.sync(*laptop_ops) == ["applied"] * 3
    assert phone.sync(*phone_ops) == ["applied"] * 3
    laptop.pull()

    assert laptop.rows == phone.rows
    items = laptop.live("checklist_items")
    assert items[item_milk]["checked"] and items[item_eggs]["checked"]
    assert laptop.note(ideas)["content"] == doc("phone version")
    assert laptop.note(ideas)["color"] == "mint"
    assert laptop.note(groceries)["pinned"] is True
    copies = [n for n in laptop.live("notes").values() if n["conflict_of"]]
    assert [(c["conflict_of"], c["content"]) for c in copies] == [(ideas, doc("laptop version"))]
    assert f"{copies[0]['id']}:{work}" in laptop.live("note_labels")


def _trash(device: Device, note_id: str, at: int) -> None:
    device.sync(device.op("note", note_id, {"trashed_at": at}))


def test_trash_purge(app: FastAPI, device: Device, settings: Settings, fake_clock: FakeClock) -> None:
    old, recent, kept, item = new_id(), new_id(), new_id(), new_id()
    for note_id in (old, recent, kept):
        device.push(device.op("note", note_id, note_fields(title="x"), base_seq=0))
    device.sync(device.op("checklist_item", item, {"note_id": old, "text": "gone", "position": "a0"}))
    _trash(device, old, fake_clock.now - 8 * DAY_MS)
    _trash(device, recent, fake_clock.now - 6 * DAY_MS)

    run_maintenance(app, clean_up=False)
    device.pull()
    assert device.note(old)["deleted"] is True
    assert device.rows["checklist_items"][item]["deleted"] is True
    assert device.note(recent)["deleted"] is False
    assert device.note(kept)["deleted"] is False

    # A device still holding an edit to the purged note learns it is gone.
    assert device.push(device.op("note", old, {"title": "late"})) == ["gone"]


def test_trash_purge_can_be_switched_off(
    app: FastAPI, device: Device, settings: Settings, fake_clock: FakeClock
) -> None:
    note_id = new_id()
    device.push(device.op("note", note_id, note_fields(), base_seq=0))
    _trash(device, note_id, 0)
    db: Database = app.state.db
    with db.writer() as session:
        off = settings.model_copy(update={"trash_retention_days": 0})
        assert maintenance.purge_expired_trash(session, off) == {}
    device.pull()
    assert device.note(note_id)["deleted"] is False


def test_nightly_cleanup(app: FastAPI, admin: TestClient, device: Device, fake_clock: FakeClock) -> None:
    invite_url(admin)
    device.push(device.op("note", new_id(), note_fields(), base_seq=0))
    db: Database = app.state.db
    with db.reader() as session:
        assert session.query(AuthSession).count() == 1
        assert session.query(Invite).count() == 1
        assert session.query(AppliedOp).count() == 1
    fake_clock.advance(200 * DAY_MS)
    run_maintenance(app, clean_up=True)
    with db.reader() as session:
        assert session.query(AuthSession).count() == 0
        assert session.query(Invite).count() == 0
        assert session.query(AppliedOp).count() == 0


def test_event_hub_coalesces_and_closes() -> None:
    async def scenario() -> None:
        hub = EventHub()
        listener = hub.subscribe("u1")
        other = hub.subscribe("u2")
        thread = threading.Thread(target=lambda: [hub.publish("u1", s) for s in (3, 5, 4)])
        thread.start()
        thread.join()
        await asyncio.wait_for(listener.wake.wait(), 1)
        assert listener.seq == 5
        assert not other.wake.is_set()
        hub.close()
        await asyncio.wait_for(other.wake.wait(), 1)
        hub.unsubscribe(listener)
        assert hub.count("u1") == 0

    asyncio.run(scenario())


def _read_event(lines: Any) -> str:
    """The data of the next `change` event, skipping heartbeats."""
    for line in lines:
        if line.startswith("data: "):
            return line.removeprefix("data: ")
    raise AssertionError("stream ended")


def test_event_stream_announces_changes(app: FastAPI, device: Device, second_device: Device) -> None:
    app.state.sse_heartbeat_s = 0.05
    second_device.push(second_device.op("note", new_id(), note_fields(), base_seq=0))
    with device.client.stream("GET", "/api/v1/sync/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no"
        lines = response.iter_lines()
        assert _read_event(lines) == "1"
        second_device.push(second_device.op("note", new_id(), note_fields(), base_seq=0))
        assert _read_event(lines) == "2"


def test_event_stream_ends_when_the_session_is_revoked(
    app: FastAPI, device: Device, second_device: Device
) -> None:
    app.state.sse_heartbeat_s = 0.05
    with device.client.stream("GET", "/api/v1/sync/events") as response:
        lines = response.iter_lines()
        _read_event(lines)
        assert second_device.client.delete("/api/v1/me/sessions").status_code == 204
        with pytest.raises(AssertionError, match="stream ended"):
            _read_event(lines)
