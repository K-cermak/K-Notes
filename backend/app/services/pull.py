from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attachment, ChecklistItem, Label, Note, NoteLabel, User
from app.schemas.sync import (
    MAX_PULL_WINDOW,
    AttachmentRow,
    Changes,
    ChecklistItemRow,
    LabelRow,
    NoteLabelRow,
    NoteRow,
    PullResponse,
)


def _rows[T: Note | ChecklistItem | Label | NoteLabel | Attachment](
    db: Session, model: type[T], user_id: str, since: int, upper: int
) -> list[T]:
    return list(
        db.scalars(select(model).where(model.user_id == user_id, model.seq > since, model.seq <= upper))
    )


def _fields(row: Any, names: tuple[str, ...]) -> dict[str, Any]:
    return {name: getattr(row, name) for name in names}


def pull(db: Session, user: User, since: int) -> PullResponse:
    """Every row changed after the cursor, in a window of at most 1000 counter values (SPEC 5.3).

    The counter is dense per user, so the window bounds the response without sorting across tables.
    Everything is read in one transaction, so the window is a consistent snapshot.
    """
    current = user.seq
    upper = min(since + MAX_PULL_WINDOW, current)
    common = ("id", "seq", "deleted")
    changes = Changes(
        notes=[
            NoteRow.model_validate(
                _fields(
                    r,
                    (
                        *common,
                        "type",
                        "title",
                        "content",
                        "color",
                        "pinned",
                        "archived",
                        "trashed_at",
                        "position",
                        "conflict_of",
                        "created_at",
                        "updated_at",
                    ),
                )
            )
            for r in _rows(db, Note, user.id, since, upper)
        ],
        checklist_items=[
            ChecklistItemRow.model_validate(_fields(r, (*common, "note_id", "text", "checked", "position")))
            for r in _rows(db, ChecklistItem, user.id, since, upper)
        ],
        labels=[
            LabelRow.model_validate(_fields(r, (*common, "name")))
            for r in _rows(db, Label, user.id, since, upper)
        ],
        note_labels=[
            NoteLabelRow.model_validate(_fields(r, (*common, "note_id", "label_id")))
            for r in _rows(db, NoteLabel, user.id, since, upper)
        ],
        attachments=[
            AttachmentRow.model_validate(
                _fields(r, (*common, "note_id", "blob_hash", "mime", "width", "height", "size", "position"))
            )
            for r in _rows(db, Attachment, user.id, since, upper)
        ],
    )
    # A cursor ahead of the server (a restored backup) gets the current counter; the client resyncs.
    return PullResponse(
        seq=max(upper, 0) if since <= current else current, has_more=upper < current, changes=changes
    )
