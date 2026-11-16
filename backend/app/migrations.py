from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine

from alembic import command

ALEMBIC_DIR = Path(__file__).resolve().parent.parent / "alembic"


def run_migrations(engine: Engine) -> None:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
