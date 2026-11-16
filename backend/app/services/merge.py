"""The single write path for note data: applies client ops with the merge rules of SPEC 5.

Every change to a synced row goes through a Batch, which bumps the user's change counter, stamps
field metadata, settles concurrent edits field by field and creates conflict copies.
"""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.models import AppliedOp, Attachment, Blob, ChecklistItem, Label, Note, NoteLabel, User
from app.models.sync import FieldMeta
from app.schemas.richtext import MAX_CONTENT_CHARS, empty_doc
from app.schemas.sync import (
    AttachmentFields,
    ChecklistItemFields,
    LabelFields,
    NoteFields,
    NoteLabelFields,
    Op,
    OpResult,
    PushRequest,
    PushResponse,
)
from app.services import clock
from app.services.positions import key_between

SERVER_DEVICE = "server"
MAX_ITEMS_PER_NOTE = 1000

# Concurrent writes to these fields keep the losing value in a conflict copy; others are settled silently.
NOTE_CONTENT = frozenset({"title", "content"})
ITEM_CONTENT = frozenset({"text"})
# Changes to these count as editing the note and move its updated_at.
NOTE_EDITS = frozenset({"type", "title", "content"})
ITEM_EDITS = frozenset({"text", "checked"})
IMMUTABLE = frozenset({"note_id", "blob_hash"})

_UUID_LENGTH = 36


class OpRejectedError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class OpGoneError(Exception):
    pass


def _empty_content() -> dict[str, Any]:
    return empty_doc().model_dump(exclude_none=True)


def _check_uuid(value: str) -> None:
    try:
        if len(value) != _UUID_LENGTH or str(uuid.UUID(value)) != value:
            raise ValueError(value)
    except ValueError:
        raise OpRejectedError("invalid_id") from None


def _validate(model: type[BaseModel], fields: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = model.model_validate(fields)
    except ValidationError as exc:
        first = exc.errors()[0]
        if first["type"] == "extra_forbidden":
            raise OpRejectedError("invalid_field") from None
        location = first["loc"][0] if first["loc"] else ""
        raise OpRejectedError("invalid_content" if location == "content" else "invalid_field") from None
    values = {name: getattr(parsed, name) for name in parsed.model_fields_set}
    if "content" in values:
        values["content"] = values["content"].model_dump(exclude_none=True)
        if len(json.dumps(values["content"], separators=(",", ":"))) > MAX_CONTENT_CHARS:
            raise OpRejectedError("too_large")
    return values


def _require(values: dict[str, Any], *names: str) -> None:
    if any(name not in values for name in names):
        raise OpRejectedError("missing_field")


def _columns(row: object) -> dict[str, Any]:
    return {attr.key: getattr(row, attr.key) for attr in inspect(row).mapper.column_attrs}


@dataclass
class _Snapshot:
    note: dict[str, Any]
    items: list[dict[str, Any]]
    label_ids: list[str]
    attachments: list[dict[str, Any]]


@dataclass
class _Conflicts:
    """Conflict bookkeeping of one op, kept apart until the op has been applied in full."""

    notes: set[str] = field(default_factory=set[str])
    lost_note: dict[str, dict[str, Any]] = field(default_factory=dict[str, dict[str, Any]])
    lost_items: dict[str, dict[str, dict[str, Any]]] = field(
        default_factory=dict[str, dict[str, dict[str, Any]]]
    )

    def lose(self, note_id: str, item_id: str | None, name: str, value: Any) -> None:
        self.notes.add(note_id)
        if item_id is None:
            self.lost_note.setdefault(note_id, {})[name] = value
        else:
            self.lost_items.setdefault(note_id, {}).setdefault(item_id, {})[name] = value

    def absorb(self, other: _Conflicts) -> None:
        self.notes |= other.notes
        for note_id, values in other.lost_note.items():
            self.lost_note.setdefault(note_id, {}).update(values)
        for note_id, items in other.lost_items.items():
            for item_id, values in items.items():
                self.lost_items.setdefault(note_id, {}).setdefault(item_id, {}).update(values)


class Batch:
    """One push (or one server-side change) for one user, applied in the caller's transaction."""

    def __init__(self, db: Session, user: User, device_id: str) -> None:
        self.db = db
        self.user = user
        self.device = device_id
        self.now = clock.now_ms()
        self.changed = False
        self._snapshots: dict[str, _Snapshot] = {}
        self._conflicts = _Conflicts()

    # Counter and stamps

    def _bump(self) -> int:
        self.user.seq += 1
        self.changed = True
        return self.user.seq

    def _stamp_new(self, row: Any, names: set[str], at: int, device: str) -> None:
        seq = self._bump()
        row.seq = seq
        row.field_meta = {name: {"seq": seq, "at": at, "dev": device} for name in names}

    def _touch_note(self, note: Note, at: int) -> None:
        note.updated_at = max(note.updated_at, at)
        note.seq = self._bump()

    # Lookups, always scoped to the user

    def _get[T](self, model: type[T], *key: str) -> T | None:
        return self.db.get(model, (self.user.id, *key))

    def _live_note(self, note_id: str) -> Note:
        note = self._get(Note, note_id)
        if note is None or note.deleted:
            raise OpGoneError
        return note

    def _children[T: ChecklistItem | Attachment | NoteLabel](self, model: type[T], note_id: str) -> list[T]:
        return list(
            self.db.scalars(
                select(model).where(
                    model.user_id == self.user.id, model.note_id == note_id, model.deleted.is_(False)
                )
            )
        )

    def _snapshot(self, note_id: str) -> None:
        """Remember a note family as it was before this batch first touched it (SPEC 5.5)."""
        if note_id in self._snapshots:
            return
        note = self._get(Note, note_id)
        if note is None or note.deleted:
            return
        self._snapshots[note_id] = _Snapshot(
            note=_columns(note),
            items=[_columns(i) for i in self._children(ChecklistItem, note_id)],
            label_ids=[m.label_id for m in self._children(NoteLabel, note_id)],
            attachments=[_columns(a) for a in self._children(Attachment, note_id)],
        )

    # Applying ops

    def apply(self, op: Op) -> OpResult:
        conflicts = _Conflicts()
        try:
            with self.db.begin_nested():
                self._apply(op, conflicts)
        except OpRejectedError as exc:
            return OpResult(op_id=op.op_id, status="rejected", error=exc.code)
        except OpGoneError:
            return OpResult(op_id=op.op_id, status="gone")
        self._conflicts.absorb(conflicts)
        return OpResult(op_id=op.op_id, status="applied")

    def _apply(self, op: Op, conflicts: _Conflicts) -> None:
        handlers = {
            "note": self._note,
            "checklist_item": self._item,
            "label": self._label,
            "note_label": self._note_label,
            "attachment": self._attachment,
        }
        handler = handlers.get(op.entity)
        if handler is None:
            raise OpRejectedError("unknown_entity")
        handler(op, conflicts)

    def _merge(
        self,
        row: Any,
        values: dict[str, Any],
        op: Op,
        content: frozenset[str],
        conflicts: _Conflicts,
        note_id: str,
        item_id: str | None = None,
    ) -> set[str]:
        """SPEC 5.4, field by field. Returns the fields whose incoming value was applied."""
        for name in IMMUTABLE & values.keys():
            if values[name] != getattr(row, name):
                raise OpRejectedError("immutable_field")
        at = min(op.edited_at, self.now)
        meta: FieldMeta = {k: dict(v) for k, v in row.field_meta.items()}
        applied: set[str] = set()
        for name, incoming in values.items():
            if name in IMMUTABLE or name == "created_at" or getattr(row, name) == incoming:
                continue
            last = meta.get(name, {"seq": 0, "at": 0, "dev": None})
            concurrent = last["seq"] > op.base_seq and last["dev"] != self.device
            if concurrent and at < last["at"]:
                if name in content:
                    conflicts.lose(note_id, item_id, name, incoming)
                continue
            if concurrent and name in content:
                # The overwritten value is already in the pre-batch snapshot the copy starts from.
                conflicts.notes.add(note_id)
            setattr(row, name, incoming)
            meta[name] = {"seq": 0, "at": at, "dev": self.device}
            applied.add(name)
        if applied:
            seq = self._bump()
            row.seq = seq
            for name in applied:
                meta[name]["seq"] = seq
            row.field_meta = meta
        return applied

    def _note(self, op: Op, conflicts: _Conflicts) -> None:
        row = self._get(Note, op.id)
        if op.kind == "purge":
            if row is None or row.deleted:
                raise OpGoneError
            self._purge_note(row)
            return
        values = _validate(NoteFields, op.fields)
        at = min(op.edited_at, self.now)
        if row is None:
            _check_uuid(op.id)
            _require(values, "type", "position")
            defaults = NoteFields().model_dump()
            data = {**defaults, "content": _empty_content(), **values}
            note = Note(
                user_id=self.user.id,
                id=op.id,
                type=data["type"],
                title=data["title"],
                content=data["content"],
                color=data["color"],
                pinned=data["pinned"],
                archived=data["archived"],
                trashed_at=data["trashed_at"],
                position=data["position"],
                conflict_of=None,
                created_at=min(values.get("created_at", at), self.now),
                updated_at=at,
                deleted=False,
            )
            self._stamp_new(note, set(defaults) - {"created_at"}, at, self.device)
            self.db.add(note)
            return
        if row.deleted:
            raise OpGoneError
        self._snapshot(row.id)
        applied = self._merge(row, values, op, NOTE_CONTENT, conflicts, note_id=row.id)
        if applied & NOTE_EDITS:
            row.updated_at = max(row.updated_at, at)

    def _item(self, op: Op, conflicts: _Conflicts) -> None:
        row = self._get(ChecklistItem, op.id)
        at = min(op.edited_at, self.now)
        if op.kind == "purge":
            if row is None or row.deleted:
                raise OpGoneError
            note = self._live_note(row.note_id)
            self._snapshot(note.id)
            self._tombstone(row)
            self._touch_note(note, at)
            return
        values = _validate(ChecklistItemFields, op.fields)
        if row is None:
            _check_uuid(op.id)
            _require(values, "note_id", "position")
            note = self._live_note(values["note_id"])
            if len(self._children(ChecklistItem, note.id)) >= MAX_ITEMS_PER_NOTE:
                raise OpRejectedError("too_large")
            self._snapshot(note.id)
            data = {**ChecklistItemFields().model_dump(), **values}
            item = ChecklistItem(user_id=self.user.id, id=op.id, deleted=False, **data)
            self._stamp_new(item, set(data), at, self.device)
            self.db.add(item)
            self._touch_note(note, at)
            return
        if row.deleted:
            raise OpGoneError
        note = self._live_note(row.note_id)
        self._snapshot(note.id)
        applied = self._merge(row, values, op, ITEM_CONTENT, conflicts, note_id=note.id, item_id=row.id)
        if applied & ITEM_EDITS:
            self._touch_note(note, at)

    def _label(self, op: Op, conflicts: _Conflicts) -> None:
        row = self._get(Label, op.id)
        if op.kind == "purge":
            if row is None or row.deleted:
                raise OpGoneError
            self._tombstone(row)
            memberships = self.db.scalars(
                select(NoteLabel).where(
                    NoteLabel.user_id == self.user.id,
                    NoteLabel.label_id == row.id,
                    NoteLabel.deleted.is_(False),
                )
            )
            for membership in memberships:
                self._tombstone(membership)
            return
        values = _validate(LabelFields, op.fields)
        at = min(op.edited_at, self.now)
        if row is None:
            _check_uuid(op.id)
            _require(values, "name")
            label = Label(user_id=self.user.id, id=op.id, name=values["name"], deleted=False)
            self._stamp_new(label, {"name"}, at, self.device)
            self.db.add(label)
            self._dedupe_label_name(label)
            return
        if row.deleted:
            raise OpGoneError
        if "name" in self._merge(row, values, op, frozenset(), conflicts, note_id=""):
            self._dedupe_label_name(row)

    def _dedupe_label_name(self, label: Label) -> None:
        """Two devices may create the same label offline; the later one becomes "Name (2)" (SPEC 4)."""
        taken = {
            name.casefold()
            for name in self.db.scalars(
                select(Label.name).where(
                    Label.user_id == self.user.id, Label.id != label.id, Label.deleted.is_(False)
                )
            )
        }
        if label.name.casefold() not in taken:
            return
        n = 2
        while True:
            suffix = f" ({n})"
            candidate = label.name[: 50 - len(suffix)] + suffix
            if candidate.casefold() not in taken:
                label.name = candidate
                return
            n += 1

    def _note_label(self, op: Op, conflicts: _Conflicts) -> None:
        note_id, _, label_id = op.id.partition(":")
        _check_uuid(note_id)
        _check_uuid(label_id)
        values = {"deleted": True} if op.kind == "purge" else _validate(NoteLabelFields, op.fields)
        note = self._live_note(note_id)
        label = self._get(Label, label_id)
        if label is None or label.deleted:
            raise OpGoneError
        row = self._get(NoteLabel, note_id, label_id)
        at = min(op.edited_at, self.now)
        if row is None:
            if values.get("deleted", False):
                raise OpGoneError
            self._snapshot(note.id)
            membership = NoteLabel(user_id=self.user.id, note_id=note_id, label_id=label_id, deleted=False)
            self._stamp_new(membership, {"deleted"}, at, self.device)
            self.db.add(membership)
            return
        # A removed label is a tombstoned membership that adding the label again revives (SPEC 4).
        self._snapshot(note.id)
        self._merge(row, values, op, frozenset(), conflicts, note_id=note.id)

    def _attachment(self, op: Op, conflicts: _Conflicts) -> None:
        row = self._get(Attachment, op.id)
        at = min(op.edited_at, self.now)
        if op.kind == "purge":
            if row is None or row.deleted:
                raise OpGoneError
            note = self._live_note(row.note_id)
            self._snapshot(note.id)
            self._tombstone(row)
            self._touch_note(note, at)
            return
        values = _validate(AttachmentFields, op.fields)
        if row is None:
            _check_uuid(op.id)
            _require(values, "note_id", "blob_hash", "mime", "width", "height", "size", "position")
            note = self._live_note(values["note_id"])
            if self._get(Blob, values["blob_hash"]) is None:
                raise OpRejectedError("blob_missing")
            self._snapshot(note.id)
            attachment = Attachment(user_id=self.user.id, id=op.id, deleted=False, **values)
            self._stamp_new(attachment, set(values), at, self.device)
            self.db.add(attachment)
            self._touch_note(note, at)
            return
        if row.deleted:
            raise OpGoneError
        note = self._live_note(row.note_id)
        self._snapshot(note.id)
        self._merge(row, values, op, frozenset(), conflicts, note_id=note.id)

    # Tombstones

    def _tombstone(self, row: Any) -> None:
        """Keep the ID and bookkeeping, clear the content (SPEC 4)."""
        row.deleted = True
        if isinstance(row, Note):
            row.title = ""
            row.content = _empty_content()
        elif isinstance(row, ChecklistItem):
            row.text = ""
        elif isinstance(row, Label):
            row.name = ""
        elif isinstance(row, Attachment):
            row.blob_hash = ""
        row.seq = self._bump()

    def _purge_note(self, note: Note) -> None:
        self._tombstone(note)
        for model in (ChecklistItem, Attachment, NoteLabel):
            for child in self._children(model, note.id):
                self._tombstone(child)

    # Conflict copies

    def finish(self) -> None:
        """Create one conflict copy per note that lost a content value in this batch (SPEC 5.5)."""
        for note_id in sorted(self._conflicts.notes):
            original = self._get(Note, note_id)
            snapshot = self._snapshots.get(note_id)
            if original is None or original.deleted or snapshot is None:
                continue
            self._copy(
                original,
                snapshot,
                self._conflicts.lost_note.get(note_id, {}),
                self._conflicts.lost_items.get(note_id, {}),
            )

    def _position_after(self, note: Note) -> str:
        following = self.db.scalar(
            select(func.min(Note.position)).where(
                Note.user_id == self.user.id, Note.deleted.is_(False), Note.position > note.position
            )
        )
        return key_between(note.position, following)

    def _copy(
        self,
        original: Note,
        snapshot: _Snapshot,
        lost_note: dict[str, Any],
        lost_items: dict[str, dict[str, Any]],
    ) -> None:
        data = {**snapshot.note, **lost_note}
        copy = Note(
            user_id=self.user.id,
            id=str(uuid.uuid4()),
            type=data["type"],
            title=data["title"],
            content=data["content"],
            color=data["color"],
            pinned=False,
            archived=data["archived"],
            trashed_at=data["trashed_at"],
            position=self._position_after(original),
            conflict_of=original.id,
            created_at=self.now,
            updated_at=self.now,
            deleted=False,
        )
        self._stamp_new(copy, set(NoteFields.model_fields) - {"created_at"}, self.now, SERVER_DEVICE)
        self.db.add(copy)
        # The models have no relationships, so the unit of work cannot order these inserts itself.
        self.db.flush()
        for item in snapshot.items:
            values = {**item, **lost_items.get(item["id"], {})}
            new_item = ChecklistItem(
                user_id=self.user.id,
                id=str(uuid.uuid4()),
                note_id=copy.id,
                text=values["text"],
                checked=values["checked"],
                position=values["position"],
                deleted=False,
            )
            self._stamp_new(new_item, set(ChecklistItemFields.model_fields), self.now, SERVER_DEVICE)
            self.db.add(new_item)
        for attachment in snapshot.attachments:
            new_attachment = Attachment(
                user_id=self.user.id,
                id=str(uuid.uuid4()),
                note_id=copy.id,
                blob_hash=attachment["blob_hash"],
                mime=attachment["mime"],
                width=attachment["width"],
                height=attachment["height"],
                size=attachment["size"],
                position=attachment["position"],
                deleted=False,
            )
            self._stamp_new(new_attachment, set(AttachmentFields.model_fields), self.now, SERVER_DEVICE)
            self.db.add(new_attachment)
        for label_id in snapshot.label_ids:
            label = self._get(Label, label_id)
            if label is None or label.deleted:
                continue
            membership = NoteLabel(user_id=self.user.id, note_id=copy.id, label_id=label_id, deleted=False)
            self._stamp_new(membership, {"deleted"}, self.now, SERVER_DEVICE)
            self.db.add(membership)


def push(db: Session, user: User, request: PushRequest) -> PushResponse:
    batch = Batch(db, user, request.device_id)
    results: list[OpResult] = []
    for op in request.ops:
        stored = db.get(AppliedOp, (user.id, op.op_id))
        if stored is not None:
            results.append(OpResult.model_validate(stored.result))
            continue
        result = batch.apply(op)
        # blob_missing is the one rejection the client retries with the same op after uploading.
        if result.error != "blob_missing":
            db.add(
                AppliedOp(user_id=user.id, op_id=op.op_id, result=result.model_dump(), created_at=batch.now)
            )
            db.flush()
        results.append(result)
    batch.finish()
    db.commit()
    return PushResponse(seq=user.seq, results=results)


def purge_note(db: Session, user: User, note: Note) -> None:
    """Permanently delete a note as the server, exactly like a client purge op (SPEC 5.7)."""
    batch = Batch(db, user, SERVER_DEVICE)
    op = Op(
        op_id=str(uuid.uuid4()),
        entity="note",
        id=note.id,
        kind="purge",
        base_seq=note.seq,
        edited_at=batch.now,
    )
    batch.apply(op)
