import json
from pathlib import Path

import pytest

from app.services.positions import InvalidKeyError, key_between, validate_key

# Generated with the fractional-indexing npm package (v4), which the client uses.
VECTORS = json.loads((Path(__file__).parent / "data" / "fractional_indexing.json").read_text())


def test_matches_the_client_library() -> None:
    for a, b, expected in VECTORS["cases"]:
        assert key_between(a, b) == expected, (a, b)


def test_keys_sort_between_their_neighbours() -> None:
    for a, b, key in VECTORS["cases"]:
        assert a is None or a < key
        assert b is None or key < b


@pytest.mark.parametrize("key", [*VECTORS["invalid"], "a0 ", "a1é"])
def test_rejects_invalid_keys(key: str) -> None:
    with pytest.raises(InvalidKeyError):
        validate_key(key)
