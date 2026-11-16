"""A minimal sync client for tests: pushes ops and keeps a local copy of what it pulled."""

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.services import clock

TABLES = ("notes", "checklist_items", "labels", "note_labels", "attachments")


def new_id() -> str:
    return str(uuid.uuid4())


class Device:
    def __init__(self, client: TestClient, device_id: str | None = None) -> None:
        self.client = client
        self.id = device_id or new_id()
        self.cursor = 0
        self.rows: dict[str, dict[str, dict[str, Any]]] = {table: {} for table in TABLES}

    def seq_of(self, table: str, row_id: str) -> int:
        row = self.rows[table].get(row_id)
        return row["seq"] if row else 0

    def op(
        self,
        entity: str,
        row_id: str,
        fields: dict[str, Any] | None = None,
        *,
        kind: str = "upsert",
        base_seq: int | None = None,
        edited_at: int | None = None,
    ) -> dict[str, Any]:
        table = {
            "note": "notes",
            "checklist_item": "checklist_items",
            "label": "labels",
            "note_label": "note_labels",
            "attachment": "attachments",
        }.get(entity, "notes")
        return {
            "op_id": new_id(),
            "entity": entity,
            "id": row_id,
            "kind": kind,
            "fields": fields or {},
            "base_seq": self.seq_of(table, row_id) if base_seq is None else base_seq,
            "edited_at": clock.now_ms() if edited_at is None else edited_at,
        }

    def push_raw(self, *ops: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post("/api/v1/sync/push", json={"device_id": self.id, "ops": list(ops)})
        assert response.status_code == 200, response.text
        return response.json()

    def push(self, *ops: dict[str, Any]) -> list[str]:
        """Push and return each op's status, with the error code for rejections."""
        results = self.push_raw(*ops)["results"]
        return [r["status"] if r["status"] != "rejected" else f"rejected:{r['error']}" for r in results]

    def pull(self) -> None:
        while True:
            response = self.client.get("/api/v1/sync/pull", params={"since": self.cursor})
            assert response.status_code == 200, response.text
            body = response.json()
            for table in TABLES:
                for row in body["changes"][table]:
                    self.rows[table][row["id"]] = row
            self.cursor = body["seq"]
            if not body["has_more"]:
                return

    def sync(self, *ops: dict[str, Any]) -> list[str]:
        statuses = self.push(*ops) if ops else []
        self.pull()
        return statuses

    def live(self, table: str) -> dict[str, dict[str, Any]]:
        return {k: v for k, v in self.rows[table].items() if not v["deleted"]}

    def note(self, note_id: str) -> dict[str, Any]:
        return self.rows["notes"][note_id]


def note_fields(**overrides: Any) -> dict[str, Any]:
    return {"type": "text", "position": "a0", **overrides}


def doc(text: str) -> dict[str, Any]:
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}
