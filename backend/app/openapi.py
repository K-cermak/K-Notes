"""Prints the OpenAPI schema without starting the server; used by `just api-types`."""

import json
import tempfile
from pathlib import Path

from app.config import Settings
from app.main import create_app


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(base_url="http://localhost", data_dir=Path(tmp)))
        print(json.dumps(app.openapi(), indent=2))


if __name__ == "__main__":
    main()
