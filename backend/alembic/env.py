import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import Connection

import app.models  # noqa: F401  # pyright: ignore[reportUnusedImport]  registers the models on Base.metadata
from alembic import context
from app.db import Base, make_engine

config = context.config
target_metadata = Base.metadata


def _migrate(connection: Connection) -> None:
    # Batch mode lets autogenerate express ALTER TABLE changes that SQLite does not support natively.
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    _migrate(connection)
else:
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)
    data_dir = Path(os.environ.get("APP_DATA_DIR", "/data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(data_dir / "app.db")
    with engine.begin() as conn:
        _migrate(conn)
