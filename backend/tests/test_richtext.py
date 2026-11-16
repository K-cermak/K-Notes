from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.richtext import RichDoc, from_plain_text, plain_text

DOC: dict[str, Any] = {
    "type": "doc",
    "content": [
        {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "Shopping"}]},
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Milk ", "marks": [{"type": "bold"}]},
                {"type": "text", "text": "and"},
                {"type": "hardBreak"},
                {"type": "text", "text": "bread", "marks": [{"type": "italic"}, {"type": "underline"}]},
            ],
        },
        {"type": "paragraph"},
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Later"}]},
    ],
}


def test_accepts_the_allowed_schema_and_extracts_plain_text() -> None:
    doc = RichDoc.model_validate(DOC)
    assert plain_text(doc) == "Shopping\nMilk and\nbread\n\nLater"
    assert doc.model_dump(exclude_none=True) == DOC


BAD: list[dict[str, Any]] = [
    {"type": "doc", "content": [{"type": "bulletList", "content": []}]},
    {"type": "doc", "content": [{"type": "heading", "attrs": {"level": 3}}]},
    {"type": "doc", "content": [{"type": "paragraph", "attrs": {"class": "x"}}]},
    {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": ""}]}]},
    {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "x", "marks": [{"type": "link", "attrs": {}}]}],
            }
        ],
    },
    {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "image", "src": "x"}]}]},
    {"type": "doc", "content": "<b>html</b>"},
    {"type": "paragraph"},
]


@pytest.mark.parametrize("bad", BAD)
def test_rejects_everything_else(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RichDoc.model_validate(bad)


def test_plain_text_round_trip() -> None:
    assert plain_text(from_plain_text("one\n\ntwo")) == "one\n\ntwo"
    assert from_plain_text("").content == []
