from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.deps import ApiAuth, CurrentApiAuth
from app.db import DbSession
from app.models import User
from app.schemas.notes_api import ApiLabel, ApiNote, ApiNoteCreate, ApiNoteList, ApiNotePatch
from app.services import notes_api
from app.services.events import EventHub

router = APIRouter(tags=["notes"])


def _device(auth: ApiAuth) -> str:
    return f"token:{auth.token.id}" if auth.token else "api"


def _announce(request: Request, user: User) -> None:
    hub: EventHub = request.app.state.events
    hub.publish(user.id, user.seq)


@router.get("/notes")
def list_notes(
    auth: CurrentApiAuth,
    db: DbSession,
    archived: Annotated[bool | None, Query(description="Leave out for both")] = False,
    trashed: bool = False,
    label: Annotated[str | None, Query(max_length=50, description="A label name")] = None,
    q: Annotated[str | None, Query(max_length=200, description="Words that must all appear")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiNoteList:
    """Notes in the order the app shows them, pinned first. Needs the read scope."""
    return notes_api.list_notes(
        db, auth.user, archived=archived, trashed=trashed, label=label, q=q, limit=limit, offset=offset
    )


@router.get("/notes/{note_id}")
def get_note(note_id: str, auth: CurrentApiAuth, db: DbSession) -> ApiNote:
    return notes_api.get_note(db, auth.user, note_id)


@router.post("/notes", status_code=status.HTTP_201_CREATED)
def create_note(body: ApiNoteCreate, request: Request, auth: CurrentApiAuth, db: DbSession) -> ApiNote:
    """Creates a text note from `text`, or a checklist from `items`, at the top. Needs the write scope."""
    note = notes_api.create_note(db, auth.user, _device(auth), body)
    _announce(request, auth.user)
    return note


@router.patch("/notes/{note_id}")
def update_note(
    note_id: str, body: ApiNotePatch, request: Request, auth: CurrentApiAuth, db: DbSession
) -> ApiNote:
    note = notes_api.update_note(db, auth.user, _device(auth), note_id, body)
    _announce(request, auth.user)
    return note


@router.delete("/notes/{note_id}")
def trash_note(note_id: str, request: Request, auth: CurrentApiAuth, db: DbSession) -> ApiNote:
    """Moves the note to the trash, from where it is purged after the retention period."""
    note = notes_api.update_note(db, auth.user, _device(auth), note_id, ApiNotePatch(trashed=True))
    _announce(request, auth.user)
    return note


@router.get("/labels")
def list_labels(auth: CurrentApiAuth, db: DbSession) -> list[ApiLabel]:
    return notes_api.list_labels(db, auth.user)
