from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.errors import NotFoundError

_IMMUTABLE = "public, max-age=31536000, immutable"
_REVALIDATE = "no-cache"


def install_spa(app: FastAPI, static_dir: Path) -> None:
    """Serve the built frontend, falling back to index.html so client-side routes survive a reload."""
    root = static_dir.resolve()
    index = root / "index.html"

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def unknown_api(path: str) -> None:  # pyright: ignore[reportUnusedFunction]
        raise NotFoundError()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        candidate = (root / path).resolve()
        if path and candidate.is_relative_to(root) and candidate.is_file():
            # Vite fingerprints everything under assets/, so those files never change.
            cache = _IMMUTABLE if path.startswith("assets/") else _REVALIDATE
            return FileResponse(candidate, headers={"Cache-Control": cache})
        if not index.is_file():
            raise NotFoundError("The frontend has not been built")
        return FileResponse(index, headers={"Cache-Control": _REVALIDATE})
