"""The small REST API for scripts (SPEC 8). Plain text in and out; rich text stays in the app."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.sync import NoteColor

LabelName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
ItemText = Annotated[str, StringConstraints(max_length=1000)]


class ApiItem(BaseModel):
    id: str
    text: str
    checked: bool


class ApiNote(BaseModel):
    id: str
    type: Literal["text", "checklist"]
    title: str
    text: str = Field(description="The body as plain text; empty for checklists")
    items: list[ApiItem]
    color: NoteColor
    pinned: bool
    archived: bool
    trashed: bool
    labels: list[str]
    created_at: int
    updated_at: int


class ApiNoteList(BaseModel):
    notes: list[ApiNote]
    total: int


class ApiNoteCreate(BaseModel):
    title: str = Field(default="", max_length=1000)
    text: str | None = Field(default=None, max_length=100_000, description="Makes a text note")
    items: list[ItemText] | None = Field(default=None, max_length=1000, description="Makes a checklist")
    color: NoteColor = "default"
    pinned: bool = False
    labels: list[LabelName] = Field(default=[], max_length=100, description="Created if missing")

    @model_validator(mode="after")
    def _text_or_items(self) -> Self:
        if self.text is not None and self.items is not None:
            raise ValueError("Give either text or items, not both")
        return self


class ApiNotePatch(BaseModel):
    title: str | None = Field(default=None, max_length=1000)
    text: str | None = Field(default=None, max_length=100_000)
    color: NoteColor | None = None
    pinned: bool | None = None
    archived: bool | None = None
    trashed: bool | None = None


class ApiLabel(BaseModel):
    id: str
    name: str
