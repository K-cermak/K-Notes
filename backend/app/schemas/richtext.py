"""The rich text document format of SPEC 4.1: a strict subset of Tiptap's JSON.

Anything outside this schema is rejected, so the server never stores markup a client could be
tricked into rendering.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Node(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _optional() -> Any:
    """An optional part that stays absent in output, as in the document the client sent."""
    return Field(default=None, exclude_if=lambda value: value is None)


class Mark(_Node):
    type: Literal["bold", "italic", "underline"]


class Text(_Node):
    type: Literal["text"]
    text: str = Field(min_length=1)
    marks: list[Mark] | None = _optional()


class HardBreak(_Node):
    type: Literal["hardBreak"]


Inline = Annotated[Text | HardBreak, Field(discriminator="type")]


class Paragraph(_Node):
    type: Literal["paragraph"]
    content: list[Inline] | None = _optional()


class HeadingAttrs(_Node):
    level: Literal[1, 2]


class Heading(_Node):
    type: Literal["heading"]
    attrs: HeadingAttrs
    content: list[Inline] | None = _optional()


Block = Annotated[Paragraph | Heading, Field(discriminator="type")]


class RichDoc(_Node):
    type: Literal["doc"]
    content: list[Block] = []


MAX_CONTENT_CHARS = 100_000


def empty_doc() -> RichDoc:
    return RichDoc(type="doc", content=[])


def plain_text(doc: RichDoc) -> str:
    """Blocks become lines, hard breaks become line breaks, marks disappear."""
    lines: list[str] = []
    for block in doc.content:
        parts: list[str] = []
        for node in block.content or []:
            parts.append(node.text if isinstance(node, Text) else "\n")
        lines.append("".join(parts))
    return "\n".join(lines)


def from_plain_text(text: str) -> RichDoc:
    content: list[Block] = [
        Paragraph(type="paragraph", content=[Text(type="text", text=line)] if line else None)
        for line in text.split("\n")
    ]
    return RichDoc(type="doc", content=content if text else [])
