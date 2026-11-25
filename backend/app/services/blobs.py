"""Image blobs (SPEC 6): content-addressed files under APP_DATA_DIR/blobs, linked to users by rows."""

import hashlib
import logging
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy import and_, delete, exists, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.models import Attachment, Blob
from app.services import clock
from app.services.clock import DAY_MS

logger = logging.getLogger(__name__)

MIME_BY_FORMAT = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}

# An upload is linked to a note only by the attachment op that follows it; until then it is kept.
UNREFERENCED_GRACE_MS = DAY_MS


class BlobTooLargeError(AppError):
    def __init__(self, limit_mb: int) -> None:
        super().__init__(413, "too_large", f"Images may be at most {limit_mb} MB")


class HashMismatchError(AppError):
    def __init__(self) -> None:
        super().__init__(400, "hash_mismatch", "The bytes do not match the hash in the URL")


class UnsupportedImageError(AppError):
    def __init__(self) -> None:
        super().__init__(415, "unsupported_image", "Only JPEG, PNG, WebP and GIF images are accepted")


def blobs_dir(settings: Settings) -> Path:
    return settings.data_dir / "blobs"


def blob_path(settings: Settings, blob_hash: str) -> Path:
    return blobs_dir(settings) / blob_hash[:2] / blob_hash[2:4] / blob_hash


def find(db: Session, user_id: str, blob_hash: str) -> Blob | None:
    return db.get(Blob, (user_id, blob_hash))


async def receive(chunks: AsyncIterator[bytes], settings: Settings, blob_hash: str, limit_mb: int) -> Path:
    """Streams an upload to a temporary file, checking its size and hash on the way."""
    limit = limit_mb * 1024 * 1024
    digest = hashlib.sha256()
    size = 0
    tmp_dir = blobs_dir(settings) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=tmp_dir)
    path = Path(name)
    try:
        with os.fdopen(handle, "wb") as out:
            async for chunk in chunks:
                size += len(chunk)
                if size > limit:
                    raise BlobTooLargeError(limit_mb)
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != blob_hash:
            raise HashMismatchError()
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def image_mime(path: Path) -> str:
    """The MIME type of an accepted image, checked by Pillow rather than trusted from the client."""
    try:
        with Image.open(path) as image:
            mime = MIME_BY_FORMAT.get(image.format or "")
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise UnsupportedImageError() from exc
    if mime is None:
        raise UnsupportedImageError()
    return mime


def store(db: Session, settings: Settings, user_id: str, blob_hash: str, upload: Path) -> None:
    """Moves a verified upload into place and links it to the user. A file already there is kept."""
    try:
        mime = image_mime(upload)
        # The row first: clean_up() holds the write lock while it deletes files nobody has a row
        # for, so once the row is in, an existing file stays, and a file it just deleted is put back.
        if find(db, user_id, blob_hash) is None:
            size = upload.stat().st_size
            db.add(Blob(user_id=user_id, hash=blob_hash, size=size, mime=mime, created_at=clock.now_ms()))
        db.commit()
        target = blob_path(settings, blob_hash)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            upload.replace(target)
    finally:
        upload.unlink(missing_ok=True)


def clean_up(db: Session, settings: Settings) -> int:
    """Unlinks blobs no live attachment of their user references, and deletes files nobody has.

    Runs after the trash purge (SPEC 5.7), in one write transaction. Returns the number of files
    deleted.
    """
    cutoff = clock.now_ms() - UNREFERENCED_GRACE_MS
    referenced = exists().where(
        and_(
            Attachment.user_id == Blob.user_id,
            Attachment.blob_hash == Blob.hash,
            Attachment.deleted.is_(False),
        )
    )
    db.execute(delete(Blob).where(Blob.created_at < cutoff, ~referenced))
    kept = set(db.scalars(select(Blob.hash).distinct()))
    removed = 0
    root = blobs_dir(settings)
    for path in root.glob("??/??/*"):
        # Files younger than the grace period may belong to an upload whose row is being written.
        if path.name in kept or path.stat().st_mtime * 1000 > cutoff:
            continue
        path.unlink(missing_ok=True)
        removed += 1
    for path in (root / "tmp").glob("*"):
        if path.stat().st_mtime * 1000 < cutoff:
            path.unlink(missing_ok=True)
    db.commit()
    if removed:
        logger.info("Deleted %d unreferenced image files", removed)
    return removed
