"""The merge rules of SPEC 5.4 and 5.5, one case per test, through the push and pull endpoints."""

from typing import Any

import pytest

from tests.conftest import FakeClock
from tests.sync_helpers import Device, doc, new_id, note_fields

MINUTE = 60_000


def _create_note(device: Device, **fields: Any) -> str:
    note_id = new_id()
    assert device.sync(device.op("note", note_id, note_fields(**fields), base_seq=0)) == ["applied"]
    return note_id


def _copies(device: Device, note_id: str) -> list[dict[str, Any]]:
    return [n for n in device.live("notes").values() if n["conflict_of"] == note_id]


def test_create_fills_defaults_and_pull_returns_the_row(device: Device) -> None:
    note_id = _create_note(device, title="Shopping")
    note = device.note(note_id)
    assert note["title"] == "Shopping"
    assert note["content"] == {"type": "doc", "content": []}
    assert (note["color"], note["pinned"], note["archived"], note["trashed_at"]) == (
        "default",
        False,
        False,
        None,
    )
    assert note["seq"] > 0
    assert note["created_at"] == note["updated_at"]


def test_clean_apply(device: Device, second_device: Device) -> None:
    note_id = _create_note(device, title="Draft")
    second_device.pull()
    assert second_device.sync(second_device.op("note", note_id, {"title": "Final"})) == ["applied"]
    device.pull()
    assert device.note(note_id)["title"] == "Final"
    assert _copies(device, note_id) == []


def test_concurrent_content_edit_later_incoming_wins(
    device: Device, second_device: Device, fake_clock: FakeClock
) -> None:
    note_id = _create_note(device, title="Original")
    second_device.pull()
    base = second_device.seq_of("notes", note_id)
    device.sync(device.op("note", note_id, {"title": "From A"}))
    fake_clock.advance(MINUTE)
    second_device.sync(second_device.op("note", note_id, {"title": "From B"}, base_seq=base))

    second_device.pull()
    assert second_device.note(note_id)["title"] == "From B"
    [copy] = _copies(second_device, note_id)
    assert copy["title"] == "From A"


def test_concurrent_content_edit_earlier_incoming_loses(
    device: Device, second_device: Device, fake_clock: FakeClock
) -> None:
    note_id = _create_note(device, title="Original")
    second_device.pull()
    base = second_device.seq_of("notes", note_id)
    edited_offline = fake_clock.now
    fake_clock.advance(MINUTE)
    device.sync(device.op("note", note_id, {"title": "From A"}))
    fake_clock.advance(MINUTE)
    # B edited before A did, but its push only arrives now.
    second_device.sync(
        second_device.op("note", note_id, {"title": "From B"}, base_seq=base, edited_at=edited_offline)
    )
    assert second_device.note(note_id)["title"] == "From A"
    [copy] = _copies(second_device, note_id)
    assert copy["title"] == "From B"


def test_same_device_follow_up_op_is_not_a_conflict(device: Device) -> None:
    note_id = _create_note(device, title="One")
    base = device.seq_of("notes", note_id)
    # Typing fast: the second op still carries the base_seq from before the first was acknowledged.
    statuses = device.sync(
        device.op("note", note_id, {"title": "One two"}, base_seq=base),
        device.op("note", note_id, {"title": "One two three"}, base_seq=base),
    )
    assert statuses == ["applied", "applied"]
    assert device.note(note_id)["title"] == "One two three"
    assert _copies(device, note_id) == []


def test_concurrent_non_content_field_is_settled_silently(
    device: Device, second_device: Device, fake_clock: FakeClock
) -> None:
    note_id = _create_note(device)
    second_device.pull()
    base = second_device.seq_of("notes", note_id)
    early = fake_clock.now
    fake_clock.advance(MINUTE)
    device.sync(device.op("note", note_id, {"color": "coral", "pinned": True}))
    second_device.sync(
        second_device.op("note", note_id, {"color": "mint", "pinned": False}, base_seq=base, edited_at=early)
    )
    note = second_device.note(note_id)
    assert (note["color"], note["pinned"]) == ("coral", True)
    assert _copies(second_device, note_id) == []


def test_future_clock_does_not_win_forever(
    device: Device, second_device: Device, fake_clock: FakeClock
) -> None:
    note_id = _create_note(device, color="default")
    second_device.pull()
    base = second_device.seq_of("notes", note_id)
    device.sync(
        device.op("note", note_id, {"color": "coral"}, edited_at=fake_clock.now + 365 * 24 * 60 * MINUTE)
    )
    fake_clock.advance(MINUTE)
    second_device.sync(second_device.op("note", note_id, {"color": "mint"}, base_seq=base))
    assert second_device.note(note_id)["color"] == "mint"


def test_equal_values_are_not_a_conflict(device: Device, second_device: Device) -> None:
    note_id = _create_note(device, title="Same")
    second_device.pull()
    base = second_device.seq_of("notes", note_id)
    device.sync(device.op("note", note_id, {"title": "Agreed"}))
    second_device.sync(second_device.op("note", note_id, {"title": "Agreed"}, base_seq=base))
    assert _copies(second_device, note_id) == []


def test_trash_on_one_device_and_edit_on_another_both_apply(device: Device, second_device: Device) -> None:
    note_id = _create_note(device, title="Old")
    second_device.pull()
    base = second_device.seq_of("notes", note_id)
    device.sync(device.op("note", note_id, {"trashed_at": 1_000}))
    second_device.sync(second_device.op("note", note_id, {"title": "New"}, base_seq=base))
    note = second_device.note(note_id)
    assert (note["title"], note["trashed_at"]) == ("New", 1_000)


def test_purge_tombstones_the_note_and_its_children(device: Device) -> None:
    note_id, item_id, label_id = _create_note(device, type="checklist", title="Secret"), new_id(), new_id()
    device.sync(
        device.op("checklist_item", item_id, {"note_id": note_id, "text": "Milk", "position": "a0"}),
        device.op("label", label_id, {"name": "Home"}),
        device.op("note_label", f"{note_id}:{label_id}"),
    )
    assert device.sync(device.op("note", note_id, kind="purge")) == ["applied"]
    note = device.note(note_id)
    assert note["deleted"] is True
    assert note["title"] == ""
    assert device.rows["checklist_items"][item_id]["deleted"] is True
    assert device.rows["checklist_items"][item_id]["text"] == ""
    assert device.rows["note_labels"][f"{note_id}:{label_id}"]["deleted"] is True
    assert device.rows["labels"][label_id]["deleted"] is False


def test_ops_on_tombstones_are_gone(device: Device, second_device: Device) -> None:
    note_id = _create_note(device)
    item_id, label_id = new_id(), new_id()
    device.sync(
        device.op("checklist_item", item_id, {"note_id": note_id, "position": "a0"}),
        device.op("label", label_id, {"name": "Work"}),
    )
    second_device.pull()
    device.sync(device.op("note", note_id, kind="purge"), device.op("label", label_id, kind="purge"))
    assert (
        second_device.push(
            second_device.op("note", note_id, {"title": "Offline edit"}),
            second_device.op("checklist_item", item_id, {"checked": True}),
            second_device.op("checklist_item", new_id(), {"note_id": note_id, "position": "a1"}),
            second_device.op("note", note_id, kind="purge"),
            second_device.op("label", label_id, {"name": "Renamed"}),
            second_device.op("note_label", f"{_create_note(second_device)}:{label_id}"),
        )
        == ["gone"] * 6
    )


def test_child_of_missing_note_is_gone(device: Device) -> None:
    assert device.push(device.op("checklist_item", new_id(), {"note_id": new_id(), "position": "a0"})) == [
        "gone"
    ]


def test_replayed_op_returns_the_stored_result(device: Device) -> None:
    note_id = new_id()
    op = device.op("note", note_id, note_fields(title="Once"), base_seq=0)
    first = device.push_raw(op)
    second = device.push_raw(op)
    assert second["results"] == first["results"]
    assert second["seq"] == first["seq"]
    rejected = device.op("note", new_id(), {"title": "no type"}, base_seq=0)
    assert device.push_raw(rejected)["results"] == device.push_raw(rejected)["results"]


def test_one_conflict_copy_per_note_per_batch(
    device: Device, second_device: Device, fake_clock: FakeClock
) -> None:
    note_id = _create_note(device, type="checklist", title="List")
    item_id = new_id()
    device.sync(device.op("checklist_item", item_id, {"note_id": note_id, "text": "Eggs", "position": "a0"}))
    second_device.pull()
    note_base, item_base = (
        second_device.seq_of("notes", note_id),
        second_device.seq_of("checklist_items", item_id),
    )
    early = fake_clock.now
    fake_clock.advance(MINUTE)
    device.sync(
        device.op("note", note_id, {"title": "List A", "content": doc("a")}),
        device.op("checklist_item", item_id, {"text": "Eggs A"}),
    )
    second_device.sync(
        second_device.op("note", note_id, {"title": "List B"}, base_seq=note_base, edited_at=early),
        second_device.op("note", note_id, {"content": doc("b")}, base_seq=note_base, edited_at=early),
        second_device.op("checklist_item", item_id, {"text": "Eggs B"}, base_seq=item_base, edited_at=early),
    )
    [copy] = _copies(second_device, note_id)
    assert (copy["title"], copy["content"]) == ("List B", doc("b"))
    [copy_item] = [i for i in second_device.live("checklist_items").values() if i["note_id"] == copy["id"]]
    assert copy_item["text"] == "Eggs B"
    assert copy_item["id"] != item_id
    original = second_device.note(note_id)
    assert (original["title"], original["content"]) == ("List A", doc("a"))
    assert second_device.rows["checklist_items"][item_id]["text"] == "Eggs A"


def test_conflict_copy_is_a_full_unpinned_copy_after_the_original(
    device: Device, second_device: Device, fake_clock: FakeClock
) -> None:
    note_id = _create_note(device, title="Trip", pinned=True, color="sage", position="a0")
    next_id = _create_note(device, position="a1")
    label_id, attachment_id, blob = new_id(), new_id(), "b" * 64
    _add_blob(device, blob)
    device.sync(
        device.op("label", label_id, {"name": "Travel"}),
        device.op("note_label", f"{note_id}:{label_id}"),
        device.op(
            "attachment",
            attachment_id,
            {
                "note_id": note_id,
                "blob_hash": blob,
                "mime": "image/jpeg",
                "width": 4,
                "height": 3,
                "size": 10,
                "position": "a0",
            },
        ),
    )
    second_device.pull()
    base = second_device.seq_of("notes", note_id)
    device.sync(device.op("note", note_id, {"title": "Trip A"}))
    fake_clock.advance(MINUTE)
    second_device.sync(second_device.op("note", note_id, {"title": "Trip B"}, base_seq=base))

    [copy] = _copies(second_device, note_id)
    assert copy["title"] == "Trip A"  # the value B's batch overwrote
    assert (copy["pinned"], copy["color"]) == (False, "sage")
    assert "a0" < copy["position"] < second_device.note(next_id)["position"]
    assert f"{copy['id']}:{label_id}" in second_device.live("note_labels")
    [copy_attachment] = [a for a in second_device.live("attachments").values() if a["note_id"] == copy["id"]]
    assert copy_attachment["blob_hash"] == blob
    assert copy_attachment["id"] != attachment_id


def test_dismissing_the_conflict_marker(device: Device, second_device: Device, fake_clock: FakeClock) -> None:
    note_id = _create_note(device, title="X")
    second_device.pull()
    base = second_device.seq_of("notes", note_id)
    device.sync(device.op("note", note_id, {"title": "A"}))
    fake_clock.advance(MINUTE)
    second_device.sync(second_device.op("note", note_id, {"title": "B"}, base_seq=base))
    [copy] = _copies(second_device, note_id)
    assert second_device.sync(second_device.op("note", copy["id"], {"conflict_of": None})) == ["applied"]
    assert _copies(second_device, note_id) == []
    assert second_device.push(second_device.op("note", copy["id"], {"conflict_of": note_id})) == [
        "rejected:invalid_field"
    ]


def test_label_name_collision_keeps_both(device: Device, second_device: Device) -> None:
    first, second, third = new_id(), new_id(), new_id()
    device.sync(device.op("label", first, {"name": "Work"}))
    second_device.sync(
        second_device.op("label", second, {"name": "work"}),
        second_device.op("label", third, {"name": " Work "}),
    )
    names = {row["id"]: row["name"] for row in second_device.live("labels").values()}
    assert names == {first: "Work", second: "work (2)", third: "Work (3)"}
    renamed = second_device.sync(second_device.op("label", third, {"name": "WORK (2)"}))
    assert renamed == ["applied"]
    assert second_device.rows["labels"][third]["name"] == "WORK (2) (2)"


def test_long_label_names_stay_within_the_limit(device: Device) -> None:
    name = "x" * 50
    device.sync(device.op("label", new_id(), {"name": name}))
    second = new_id()
    device.sync(device.op("label", second, {"name": name}))
    assert device.rows["labels"][second]["name"] == "x" * 46 + " (2)"


def test_label_removal_and_re_adding(device: Device) -> None:
    note_id, label_id = _create_note(device), new_id()
    membership = f"{note_id}:{label_id}"
    device.sync(device.op("label", label_id, {"name": "Ideas"}), device.op("note_label", membership))
    assert device.sync(device.op("note_label", membership, kind="purge")) == ["applied"]
    assert device.rows["note_labels"][membership]["deleted"] is True
    assert device.sync(device.op("note_label", membership, {"deleted": False})) == ["applied"]
    assert device.rows["note_labels"][membership]["deleted"] is False


def test_deleting_a_label_removes_it_from_notes_and_keeps_them(device: Device) -> None:
    note_id, label_id = _create_note(device, title="Keep me"), new_id()
    device.sync(
        device.op("label", label_id, {"name": "Old"}), device.op("note_label", f"{note_id}:{label_id}")
    )
    device.sync(device.op("label", label_id, kind="purge"))
    assert device.rows["note_labels"][f"{note_id}:{label_id}"]["deleted"] is True
    assert device.note(note_id)["deleted"] is False


def test_updated_at_moves_only_on_content_edits(device: Device, fake_clock: FakeClock) -> None:
    note_id = _create_note(device)
    created = device.note(note_id)["updated_at"]
    fake_clock.advance(MINUTE)
    device.sync(device.op("note", note_id, {"color": "coral", "pinned": True, "position": "a5"}))
    assert device.note(note_id)["updated_at"] == created
    device.sync(device.op("note", note_id, {"title": "Edited"}))
    after_title = device.note(note_id)["updated_at"]
    assert after_title == created + MINUTE
    fake_clock.advance(MINUTE)
    device.sync(device.op("checklist_item", new_id(), {"note_id": note_id, "position": "a0"}))
    assert device.note(note_id)["updated_at"] == after_title + MINUTE


INVALID_OPS: list[tuple[tuple[str, dict[str, Any]], str]] = [
    (("note", {"title": "no type or position"}), "missing_field"),
    (("note", {**note_fields(), "colour": "red"}), "invalid_field"),
    (("note", note_fields(color="red")), "invalid_field"),
    (("note", note_fields(pinned="yes")), "invalid_field"),
    (("note", note_fields(position="a00")), "invalid_field"),
    (("note", note_fields(title="x" * 1001)), "invalid_field"),
    (("note", note_fields(content={"type": "doc", "content": [{"type": "script"}]})), "invalid_content"),
    (("note", note_fields(content=doc("x" * 100_001))), "too_large"),
    (("label", {"name": "  "}), "invalid_field"),
    (("folder", {}), "unknown_entity"),
]


@pytest.mark.parametrize(("op", "error"), INVALID_OPS)
def test_invalid_ops_are_rejected(device: Device, op: tuple[str, dict[str, Any]], error: str) -> None:
    entity, fields = op
    assert device.push(device.op(entity, new_id(), fields, base_seq=0)) == [f"rejected:{error}"]


def test_ids_must_be_uuids(device: Device) -> None:
    assert device.push(device.op("note", "not-a-uuid", note_fields())) == ["rejected:invalid_id"]
    assert device.push(device.op("note_label", "a:b")) == ["rejected:invalid_id"]


def test_immutable_fields_cannot_change(device: Device) -> None:
    note_id, other_id, item_id = _create_note(device), _create_note(device), new_id()
    device.sync(device.op("checklist_item", item_id, {"note_id": note_id, "position": "a0"}))
    assert device.push(device.op("checklist_item", item_id, {"note_id": other_id})) == [
        "rejected:immutable_field"
    ]


def test_a_rejected_op_does_not_affect_the_rest_of_the_batch(device: Device) -> None:
    good, bad = new_id(), new_id()
    statuses = device.sync(
        device.op("note", good, note_fields(title="Good"), base_seq=0),
        device.op("note", bad, note_fields(color="neon"), base_seq=0),
        device.op("note", good, {"title": "Still good"}),
    )
    assert statuses == ["applied", "rejected:invalid_field", "applied"]
    assert device.note(good)["title"] == "Still good"
    assert bad not in device.rows["notes"]


def test_item_limit_per_note(device: Device, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import merge

    monkeypatch.setattr(merge, "MAX_ITEMS_PER_NOTE", 2)
    note_id = _create_note(device, type="checklist")
    ops = [
        device.op("checklist_item", new_id(), {"note_id": note_id, "position": f"a{i}"}) for i in (1, 2, 3)
    ]
    assert device.push(*ops) == ["applied", "applied", "rejected:too_large"]


def _add_blob(device: Device, blob_hash: str) -> None:
    from fastapi import FastAPI

    from app.db import Database
    from app.models import Blob

    app: FastAPI = device.client.app  # pyright: ignore[reportAssignmentType]
    db: Database = app.state.db
    user_id = device.client.get("/api/v1/me").json()["id"]
    with db.writer() as session:
        session.add(Blob(user_id=user_id, hash=blob_hash, size=10, mime="image/jpeg", created_at=0))
        session.commit()


def test_attachment_waits_for_its_blob(device: Device) -> None:
    note_id, attachment_id, blob = _create_note(device), new_id(), "a" * 64
    op = device.op(
        "attachment",
        attachment_id,
        {
            "note_id": note_id,
            "blob_hash": blob,
            "mime": "image/png",
            "width": 2,
            "height": 2,
            "size": 5,
            "position": "a0",
        },
    )
    assert device.push(op) == ["rejected:blob_missing"]
    _add_blob(device, blob)
    # The client retries the very same op after uploading, so blob_missing must not be remembered.
    assert device.sync(op) == ["applied"]
    assert device.rows["attachments"][attachment_id]["blob_hash"] == blob


def test_attachment_purge_clears_the_blob_reference(device: Device) -> None:
    note_id, attachment_id, blob = _create_note(device), new_id(), "c" * 64
    _add_blob(device, blob)
    device.sync(
        device.op(
            "attachment",
            attachment_id,
            {
                "note_id": note_id,
                "blob_hash": blob,
                "mime": "image/gif",
                "width": 1,
                "height": 1,
                "size": 1,
                "position": "a0",
            },
        )
    )
    device.sync(device.op("attachment", attachment_id, kind="purge"))
    assert device.rows["attachments"][attachment_id]["deleted"] is True
    assert device.rows["attachments"][attachment_id]["blob_hash"] == ""


def test_too_many_ops_in_one_push(device: Device) -> None:
    ops = [device.op("note", new_id(), note_fields(), base_seq=0) for _ in range(201)]
    response = device.client.post("/api/v1/sync/push", json={"device_id": device.id, "ops": ops})
    assert response.status_code == 422
