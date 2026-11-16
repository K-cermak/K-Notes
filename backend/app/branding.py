import json
from functools import cache
from pathlib import Path

from pydantic import BaseModel

# The image keeps the repository layout, so the same relative path works in development and in Docker.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Branding(BaseModel):
    name: str
    short_name: str
    description: str
    theme_color: str


@cache
def get_branding() -> Branding:
    return Branding.model_validate(json.loads((REPO_ROOT / "branding.json").read_text()))
