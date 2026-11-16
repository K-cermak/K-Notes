from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.branding import get_branding
from app.config import Settings
from app.main import create_app
from app.version import VERSION


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_reports_instance_settings(client: TestClient) -> None:
    body = client.get("/api/v1/config").json()
    assert body["app_name"] == get_branding().name
    assert body["version"] == VERSION
    assert body["password_login_enabled"] is True
    assert body["oidc_enabled"] is False
    assert body["trash_retention_days"] == 7
    assert body["max_image_mb"] == 10


def test_startup_creates_data_dir_database_and_secret(client: TestClient, settings: Settings) -> None:
    assert settings.database_path.exists()
    assert (settings.data_dir / "blobs").is_dir()
    secret = (settings.data_dir / "secret.key").read_text()
    assert len(secret) >= 32
    assert settings.resolved_secret_key == secret


def test_sqlite_pragmas(client: TestClient) -> None:
    engine: Engine = cast(FastAPI, client.app).state.engine
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
        assert connection.exec_driver_sql("PRAGMA synchronous").scalar() == 1


def test_unknown_api_path_returns_error_shape(client: TestClient) -> None:
    for method in ("GET", "POST", "DELETE"):
        response = client.request(method, "/api/v1/nope")
        assert response.status_code == 404
        assert response.json() == {"code": "not_found", "message": "Not found"}


def test_validation_error_shape(settings: Settings, static_dir: Path) -> None:
    app = create_app(settings, static_dir=static_dir)

    @app.get("/api/v1/test-validation", include_in_schema=False)
    def needs_int(n: int) -> int:  # pyright: ignore[reportUnusedFunction]
        return n

    # Routes match in order, so move the test route ahead of the catch-alls.
    app.router.routes.insert(0, app.router.routes.pop())
    with TestClient(app) as client:
        response = client.get("/api/v1/test-validation", params={"n": "x"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["message"].startswith("query.n:")
