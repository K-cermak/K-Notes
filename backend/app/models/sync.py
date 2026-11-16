from typing import Any

from sqlalchemy import JSON, ForeignKey, ForeignKeyConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

FieldMeta = dict[str, dict[str, Any]]


class Synced:
    """Bookkeeping columns every synced row carries (SPEC 4).

    Rows are keyed by (user_id, id): IDs come from clients, so one user's ID can never reach or
    collide with another user's row.
    """

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, sort_order=-1
    )
    seq: Mapped[int]
    field_meta: Mapped[FieldMeta] = mapped_column(JSON, default=dict)
    deleted: Mapped[bool] = mapped_column(default=False)


def _table_args(table: str, *extra: Any, child: bool = False) -> tuple[Any, ...]:
    """The pull index on (user_id, seq), and for children of a note the key to their note."""
    args: list[Any] = [Index(f"ix_{table}_user_seq", "user_id", "seq")]
    if child:
        args.append(
            ForeignKeyConstraint(["user_id", "note_id"], ["notes.user_id", "notes.id"], ondelete="CASCADE")
        )
        args.append(Index(f"ix_{table}_note", "user_id", "note_id"))
    return (*args, *extra)


class Note(Synced, Base):
    __tablename__ = "notes"
    __table_args__ = _table_args("notes")

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(10))
    title: Mapped[str]
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    color: Mapped[str] = mapped_column(String(16))
    pinned: Mapped[bool]
    archived: Mapped[bool]
    trashed_at: Mapped[int | None]
    position: Mapped[str] = mapped_column(String(128))
    conflict_of: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[int]
    updated_at: Mapped[int]


class ChecklistItem(Synced, Base):
    __tablename__ = "checklist_items"
    __table_args__ = _table_args("checklist_items", child=True)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    note_id: Mapped[str] = mapped_column(String(36))
    text: Mapped[str]
    checked: Mapped[bool]
    position: Mapped[str] = mapped_column(String(128))


class Label(Synced, Base):
    __tablename__ = "labels"
    __table_args__ = _table_args("labels")

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class NoteLabel(Synced, Base):
    __tablename__ = "note_labels"
    __table_args__ = _table_args(
        "note_labels",
        ForeignKeyConstraint(["user_id", "label_id"], ["labels.user_id", "labels.id"], ondelete="CASCADE"),
        Index("ix_note_labels_label", "user_id", "label_id"),
        child=True,
    )

    note_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    label_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    @property
    def id(self) -> str:
        return f"{self.note_id}:{self.label_id}"


class Attachment(Synced, Base):
    __tablename__ = "attachments"
    __table_args__ = _table_args("attachments", child=True)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    note_id: Mapped[str] = mapped_column(String(36))
    blob_hash: Mapped[str] = mapped_column(String(64))
    mime: Mapped[str] = mapped_column(String(32))
    width: Mapped[int]
    height: Mapped[int]
    size: Mapped[int]
    position: Mapped[str] = mapped_column(String(128))


class AppliedOp(Base):
    """Results of pushed ops, so a retried push is answered without applying anything twice."""

    __tablename__ = "applied_ops"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    op_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(index=True)


class Blob(Base):
    __tablename__ = "blobs"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    size: Mapped[int]
    mime: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[int]
