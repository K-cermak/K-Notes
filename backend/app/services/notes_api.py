"""The REST API for scripts (SPEC 8): reads the stored rows and writes by building ops for merge.push.

Like every other write, it goes through the merge service, with the token's ID as the device ID.
"""

import unicodedata
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.models import ChecklistItem, Label, Note, NoteLabel, User
from app.schemas.notes_api import ApiItem, ApiLabel, ApiNote, ApiNoteCreate, ApiNoteList, ApiNotePatch
from app.schemas.richtext import RichDoc, from_plain_text, plain_text
from app.schemas.sync import MAX_OPS_PER_PUSH, Op, PushRequest
from app.services import clock, merge, storage
from app.services.positions import key_between


def fold(text: str) -> str:
    """Case and diacritics folding, as the app's search does (SPEC 9)."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _live[T: Note | ChecklistItem | Label | NoteLabel](db: Session, model: type[T], user: User) -> list[T]:
    return list(db.scalars(select(model).where(model.user_id == user.id, model.deleted.is_(False))))


def _note_view(note: Note, items: list[ChecklistItem], labels: list[str]) -> ApiNote:
    return ApiNote(
        id=note.id,
        type=note.type,  # pyright: ignore[reportArgumentType]
        title=note.title,
        text=plain_text(RichDoc.model_validate(note.content)) if note.type == "text" else "",
        items=[
            ApiItem(id=item.id, text=item.text, checked=item.checked)
            for item in sorted(items, key=lambda i: (i.position, i.id))
        ],
        color=note.color,  # pyright: ignore[reportArgumentType]
        pinned=note.pinned,
        archived=note.archived,
        trashed=note.trashed_at is not None,
        labels=sorted(labels, key=str.lower),
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _views(db: Session, user: User, notes: list[Note]) -> list[ApiNote]:
    items: dict[str, list[ChecklistItem]] = defaultdict(list)
    for item in _live(db, ChecklistItem, user):
        items[item.note_id].append(item)
    names = {label.id: label.name for label in _live(db, Label, user)}
    labels: dict[str, list[str]] = defaultdict(list)
    for membership in _live(db, NoteLabel, user):
        if membership.label_id in names:
            labels[membership.note_id].append(names[membership.label_id])
    return [_note_view(note, items[note.id], labels[note.id]) for note in notes]


def list_notes(
    db: Session,
    user: User,
    *,
    archived: bool | None,
    trashed: bool,
    label: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> ApiNoteList:
    notes = [
        note
        for note in _live(db, Note, user)
        if (note.trashed_at is not None) == trashed and (archived is None or note.archived == archived)
    ]
    notes.sort(key=lambda n: (not n.pinned, n.position, n.id))
    views = _views(db, user, notes)
    if label is not None:
        wanted = label.strip().lower()
        views = [v for v in views if any(name.lower() == wanted for name in v.labels)]
    if q:
        terms = fold(q).split()
        views = [
            v
            for v in views
            if all(
                term in fold("\n".join([v.title, v.text, *(i.text for i in v.items), *v.labels]))
                for term in terms
            )
        ]
    return ApiNoteList(notes=views[offset : offset + limit], total=len(views))


def _get_note(db: Session, user: User, note_id: str) -> Note:
    note = db.get(Note, (user.id, note_id))
    if note is None or note.deleted:
        raise NotFoundError()
    return note


def get_note(db: Session, user: User, note_id: str) -> ApiNote:
    return _views(db, user, [_get_note(db, user, note_id)])[0]


def list_labels(db: Session, user: User) -> list[ApiLabel]:
    labels = sorted(_live(db, Label, user), key=lambda label: label.name.lower())
    return [ApiLabel(id=label.id, name=label.name) for label in labels]


def _op(entity: str, row_id: str, fields: dict[str, Any], base_seq: int, now: int) -> Op:
    return Op(
        op_id=str(uuid.uuid4()),
        entity=entity,
        id=row_id,
        kind="upsert",
        fields=fields,
        base_seq=base_seq,
        edited_at=now,
    )


def _push(db: Session, user: User, device_id: str, ops: list[Op]) -> None:
    for start in range(0, len(ops), MAX_OPS_PER_PUSH):
        response = merge.push(
            db, user, PushRequest(device_id=device_id, ops=ops[start : start + MAX_OPS_PER_PUSH])
        )
        refused = next((r for r in response.results if r.status != "applied"), None)
        if refused is not None:
            raise InvalidInputError(refused.error or refused.status, "The change could not be saved")


def create_note(db: Session, user: User, device_id: str, body: ApiNoteCreate) -> ApiNote:
    # Only here: sync and uploads accept changes over the quota, as they may have been made offline.
    if storage.status(db, user).full:
        raise ConflictError("storage_full", "Your storage is full. Delete notes or images to make room.")
    now = clock.now_ms()
    note_id = str(uuid.uuid4())
    first = db.scalar(select(func.min(Note.position)).where(Note.user_id == user.id, Note.deleted.is_(False)))
    checklist = body.items is not None
    content = from_plain_text(body.text or "") if not checklist else from_plain_text("")
    ops = [
        _op(
            "note",
            note_id,
            {
                "type": "checklist" if checklist else "text",
                "title": body.title,
                "content": content.model_dump(),
                "color": body.color,
                "pinned": body.pinned,
                "position": key_between(None, first),
                "created_at": now,
            },
            0,
            now,
        )
    ]
    position: str | None = None
    for text in body.items or []:
        position = key_between(position, None)
        ops.append(
            _op(
                "checklist_item",
                str(uuid.uuid4()),
                {"note_id": note_id, "text": text, "position": position},
                0,
                now,
            )
        )
    existing = {label.name.lower(): label.id for label in _live(db, Label, user)}
    for name in dict.fromkeys(body.labels):
        label_id = existing.get(name.lower())
        if label_id is None:
            label_id = existing[name.lower()] = str(uuid.uuid4())
            ops.append(_op("label", label_id, {"name": name}, 0, now))
        ops.append(_op("note_label", f"{note_id}:{label_id}", {}, 0, now))
    _push(db, user, device_id, ops)
    return get_note(db, user, note_id)


def update_note(db: Session, user: User, device_id: str, note_id: str, body: ApiNotePatch) -> ApiNote:
    note = _get_note(db, user, note_id)
    now = clock.now_ms()
    fields: dict[str, Any] = body.model_dump(exclude_none=True, exclude={"text", "trashed"})
    if body.text is not None:
        if note.type != "text":
            raise ConflictError("not_text_note", "A checklist has items rather than text")
        fields["content"] = from_plain_text(body.text).model_dump()
    if body.trashed is not None:
        fields["trashed_at"] = now if body.trashed else None
    if body.archived:
        fields["pinned"] = False
    if fields:
        # Based on what the server holds now, so the change is never treated as concurrent.
        _push(db, user, device_id, [_op("note", note_id, fields, note.seq, now)])
    return get_note(db, user, note_id)
