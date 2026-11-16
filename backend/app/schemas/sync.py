from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.richtext import RichDoc, empty_doc
from app.services.positions import InvalidKeyError, validate_key

MAX_OPS_PER_PUSH = 200
MAX_PULL_WINDOW = 1000

Entity = Literal["note", "checklist_item", "label", "note_label", "attachment"]
NoteColor = Literal[
    "default", "coral", "peach", "sand", "mint", "sage", "fog", "storm", "dusk", "blossom", "clay", "chalk"
]
ImageMime = Literal["image/jpeg", "image/png", "image/webp", "image/gif"]
Uuid = Annotated[
    str, StringConstraints(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
]
Timestamp = Annotated[int, Field(ge=0)]


def _check_position(value: str) -> str:
    try:
        validate_key(value)
    except InvalidKeyError as exc:
        raise ValueError("invalid position") from exc
    return value


Position = Annotated[str, StringConstraints(max_length=128), AfterValidator(_check_position)]


class Op(BaseModel):
    op_id: Uuid
    entity: str = Field(max_length=32)
    id: str = Field(max_length=80)
    kind: Literal["upsert", "purge"]
    fields: dict[str, Any] = {}
    base_seq: int = Field(ge=0)
    edited_at: Timestamp


class PushRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    ops: list[Op] = Field(max_length=MAX_OPS_PER_PUSH)


class OpResult(BaseModel):
    op_id: str
    status: Literal["applied", "gone", "rejected"]
    error: str | None = None


class PushResponse(BaseModel):
    seq: int
    results: list[OpResult]


# The fields a client may set on each entity. A field left out of an op is not in model_fields_set;
# the defaults fill in a newly created row.


class _Fields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NoteFields(_Fields):
    type: Literal["text", "checklist"] = "text"
    title: Annotated[str, StringConstraints(max_length=1000)] = ""
    content: RichDoc = Field(default_factory=empty_doc)
    color: NoteColor = "default"
    pinned: bool = False
    archived: bool = False
    trashed_at: Timestamp | None = None
    position: Position = ""
    # Clients can only dismiss the conflict marker; the server sets it on conflict copies.
    conflict_of: None = None
    created_at: Timestamp = 0


class ChecklistItemFields(_Fields):
    note_id: Uuid = ""
    text: Annotated[str, StringConstraints(max_length=1000)] = ""
    checked: bool = False
    position: Position = ""


class LabelFields(_Fields):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] = ""


class NoteLabelFields(_Fields):
    deleted: bool = False


class AttachmentFields(_Fields):
    note_id: Uuid = ""
    blob_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")] = ""
    mime: ImageMime = "image/jpeg"
    width: Annotated[int, Field(ge=1, le=100_000)] = 1
    height: Annotated[int, Field(ge=1, le=100_000)] = 1
    size: Annotated[int, Field(ge=0)] = 0
    position: Position = ""


class _Row(BaseModel):
    id: str
    seq: int
    deleted: bool


class NoteRow(_Row):
    type: Literal["text", "checklist"]
    title: str
    content: RichDoc
    color: NoteColor
    pinned: bool
    archived: bool
    trashed_at: int | None
    position: str
    conflict_of: str | None
    created_at: int
    updated_at: int


class ChecklistItemRow(_Row):
    note_id: str
    text: str
    checked: bool
    position: str


class LabelRow(_Row):
    name: str


class NoteLabelRow(_Row):
    note_id: str
    label_id: str


class AttachmentRow(_Row):
    note_id: str
    blob_hash: str
    mime: str
    width: int
    height: int
    size: int
    position: str


class Changes(BaseModel):
    notes: list[NoteRow] = []
    checklist_items: list[ChecklistItemRow] = []
    labels: list[LabelRow] = []
    note_labels: list[NoteLabelRow] = []
    attachments: list[AttachmentRow] = []


class PullResponse(BaseModel):
    seq: int
    has_more: bool
    changes: Changes
