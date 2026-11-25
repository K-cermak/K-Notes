from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Path, Request, Response, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import SESSION_COOKIE, CurrentAuth, session_user
from app.config import Settings
from app.db import Database, DbSession
from app.errors import ErrorResponse, NotFoundError, UnauthorizedError
from app.services import blobs, limits

router = APIRouter(prefix="/blobs", tags=["blobs"])

BlobHash = Annotated[str, Path(pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the bytes, in hex")]

# Blobs never change, so a browser may keep them for good; private keeps shared caches out.
CACHE_FOREVER = "private, immutable, max-age=31536000"


@router.head("/{blob_hash}", responses={404: {"description": "Not uploaded by this user"}})
def head_blob(blob_hash: BlobHash, auth: CurrentAuth, db: DbSession) -> Response:
    """Whether this user has the blob, so the client knows if it has to upload it."""
    if blobs.find(db, auth.user.id, blob_hash) is None:
        raise NotFoundError()
    return Response(status_code=status.HTTP_200_OK)


def _max_image_mb(database: Database) -> int:
    with database.reader() as db:
        return limits.max_image_mb(db)


def _store(database: Database, settings: Settings, user_id: str, blob_hash: str, upload: FilePath) -> None:
    with database.writer() as db:
        blobs.store(db, settings, user_id, blob_hash, upload)


@router.put(
    "/{blob_hash}",
    status_code=status.HTTP_204_NO_CONTENT,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
    responses={
        400: {"model": ErrorResponse, "description": "The bytes do not match the hash"},
        413: {"model": ErrorResponse, "description": "Larger than the limit set by an admin"},
        415: {"model": ErrorResponse, "description": "Not a JPEG, PNG, WebP or GIF image"},
    },
)
async def upload_blob(blob_hash: BlobHash, request: Request) -> None:
    """Uploads image bytes. Uploading a blob the server already has is harmless."""
    # The body is streamed to disk before any write transaction starts, so a slow upload never
    # holds the database's write lock; the session is checked in a short read of its own.
    database: Database = request.app.state.db
    settings: Settings = request.app.state.settings
    found = await run_in_threadpool(session_user, database, request.cookies.get(SESSION_COOKIE))
    if found is None:
        raise UnauthorizedError()
    limit_mb = await run_in_threadpool(_max_image_mb, database)
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > limit_mb * 1024 * 1024:
        raise blobs.BlobTooLargeError(limit_mb)
    upload = await blobs.receive(request.stream(), settings, blob_hash, limit_mb)
    await run_in_threadpool(_store, database, settings, found[0], blob_hash, upload)


@router.get(
    "/{blob_hash}",
    response_class=FileResponse,
    responses={
        200: {"content": {"image/*": {}}, "description": "The image bytes"},
        404: {"model": ErrorResponse, "description": "Not found for this user"},
    },
)
def get_blob(blob_hash: BlobHash, request: Request, auth: CurrentAuth, db: DbSession) -> FileResponse:
    """The image bytes. Only a user linked to the blob can read it; knowing the hash is not enough."""
    settings: Settings = request.app.state.settings
    blob = blobs.find(db, auth.user.id, blob_hash)
    path = blobs.blob_path(settings, blob_hash)
    if blob is None or not path.is_file():
        raise NotFoundError()
    return FileResponse(path, media_type=blob.mime, headers={"Cache-Control": CACHE_FOREVER})
