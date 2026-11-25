import hashlib
import io
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.db import Database
from app.main import run_maintenance
from app.models import Blob
from app.services import blobs
from app.services.clock import DAY_MS
from tests.conftest import FakeClock
from tests.sync_helpers import Device, new_id, note_fields


def image_bytes(fmt: str = "PNG", color: str = "red", size: tuple[int, int] = (4, 3)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format=fmt)
    return out.getvalue()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def upload(client: TestClient, data: bytes, blob_hash: str | None = None) -> Any:
    return client.put(
        f"/api/v1/blobs/{blob_hash or sha(data)}",
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )


def attach(device: Device, blob_hash: str, note_id: str | None = None) -> tuple[str, str]:
    note_id = note_id or new_id()
    attachment_id = new_id()
    device.sync(
        device.op("note", note_id, note_fields(), base_seq=0),
        device.op(
            "attachment",
            attachment_id,
            {
                "note_id": note_id,
                "blob_hash": blob_hash,
                "mime": "image/png",
                "width": 4,
                "height": 3,
                "size": 10,
                "position": "a0",
            },
        ),
    )
    return note_id, attachment_id


def test_blob_endpoints_need_a_session(client: TestClient) -> None:
    data = image_bytes()
    assert client.head(f"/api/v1/blobs/{sha(data)}").status_code == 401
    assert client.get(f"/api/v1/blobs/{sha(data)}").status_code == 401
    assert upload(client, data).status_code == 401


def test_upload_check_and_download(device: Device, settings: Settings) -> None:
    data = image_bytes("JPEG")
    blob_hash = sha(data)
    client = device.client
    assert client.head(f"/api/v1/blobs/{blob_hash}").status_code == 404
    assert upload(client, data).status_code == 204
    assert client.head(f"/api/v1/blobs/{blob_hash}").status_code == 200

    response = client.get(f"/api/v1/blobs/{blob_hash}")
    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "private, immutable, max-age=31536000"
    assert blobs.blob_path(settings, blob_hash).read_bytes() == data


def test_the_same_bytes_are_stored_once(
    app: FastAPI, device: Device, make_user: Callable[..., TestClient], settings: Settings
) -> None:
    data = image_bytes()
    other = make_user("b@example.com")
    for client in (device.client, device.client, other):
        assert upload(client, data).status_code == 204
    files = [p for p in blobs.blobs_dir(settings).glob("??/??/*")]
    assert [p.name for p in files] == [sha(data)]
    db: Database = app.state.db
    with db.reader() as session:
        assert session.query(Blob).count() == 2


def test_a_hash_is_not_enough_to_read_someone_elses_blob(
    device: Device, make_user: Callable[..., TestClient]
) -> None:
    data = image_bytes()
    assert upload(device.client, data).status_code == 204
    intruder = make_user("b@example.com")
    assert intruder.head(f"/api/v1/blobs/{sha(data)}").status_code == 404
    response = intruder.get(f"/api/v1/blobs/{sha(data)}")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_uploads_are_verified(device: Device, settings: Settings) -> None:
    data = image_bytes()
    wrong = upload(device.client, data, "0" * 64)
    assert (wrong.status_code, wrong.json()["code"]) == (400, "hash_mismatch")

    text = b"<svg xmlns='http://www.w3.org/2000/svg'/>"
    not_image = upload(device.client, text)
    assert (not_image.status_code, not_image.json()["code"]) == (415, "unsupported_image")

    bmp = image_bytes("BMP")
    assert upload(device.client, bmp).status_code == 415

    assert device.client.put("/api/v1/blobs/not-a-hash", content=data).status_code == 422
    assert list(blobs.blobs_dir(settings).glob("??/??/*")) == []
    assert list((blobs.blobs_dir(settings) / "tmp").glob("*")) == []


def test_uploads_over_the_limit_are_refused(admin: TestClient, device: Device) -> None:
    assert admin.patch("/api/v1/admin/settings", json={"max_image_mb": 1}).status_code == 200
    data = image_bytes("PNG") + b"\0" * (1024 * 1024)
    response = upload(device.client, data)
    assert (response.status_code, response.json()["code"]) == (413, "too_large")

    # A chunked upload has no Content-Length; the limit is enforced while streaming.
    chunked = device.client.put(f"/api/v1/blobs/{sha(data)}", content=iter([data[:1000], data[1000:]]))
    assert chunked.status_code == 413


def test_accepted_formats(device: Device) -> None:
    for fmt in ("PNG", "JPEG", "WEBP", "GIF"):
        assert upload(device.client, image_bytes(fmt, color="blue")).status_code == 204, fmt


def test_cleanup_after_purge(app: FastAPI, device: Device, settings: Settings, fake_clock: FakeClock) -> None:
    kept, purged, shared, unattached = (image_bytes(color=c) for c in ("red", "green", "blue", "white"))
    for data in (kept, purged, shared, unattached):
        assert upload(device.client, data).status_code == 204
    attach(device, sha(kept))
    gone_note, _ = attach(device, sha(purged))
    shared_a, _ = attach(device, sha(shared))
    attach(device, sha(shared))
    device.sync(device.op("note", gone_note, kind="purge"), device.op("note", shared_a, kind="purge"))

    # A fresh upload may still be waiting for its attachment op, so nothing goes at once.
    run_maintenance(app, clean_up=False)
    assert all(blobs.blob_path(settings, sha(d)).exists() for d in (kept, purged, shared, unattached))

    fake_clock.advance(2 * DAY_MS)
    run_maintenance(app, clean_up=False)
    assert blobs.blob_path(settings, sha(kept)).exists()
    assert blobs.blob_path(settings, sha(shared)).exists()
    assert not blobs.blob_path(settings, sha(purged)).exists()
    assert not blobs.blob_path(settings, sha(unattached)).exists()
    assert device.client.head(f"/api/v1/blobs/{sha(purged)}").status_code == 404
    assert device.client.get(f"/api/v1/blobs/{sha(shared)}").status_code == 200


def test_cleanup_keeps_a_file_another_user_still_has(
    app: FastAPI, device: Device, make_user: Callable[..., TestClient], fake_clock: FakeClock
) -> None:
    data = image_bytes()
    other = Device(make_user("b@example.com"))
    for client in (device.client, other.client):
        assert upload(client, data).status_code == 204
    attach(other, sha(data))
    fake_clock.advance(2 * DAY_MS)
    run_maintenance(app, clean_up=False)
    assert device.client.head(f"/api/v1/blobs/{sha(data)}").status_code == 404
    assert other.client.get(f"/api/v1/blobs/{sha(data)}").content == data
