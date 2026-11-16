from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import Connection, Engine, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _on_connect(dbapi_connection: Any, _record: Any) -> None:
    # SQLAlchemy emits BEGIN itself (see _begin), so sqlite3 must not start transactions on its own.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def make_engine(path: Path, *, immediate: bool = False) -> Engine:
    """An engine whose transactions start with BEGIN, or BEGIN IMMEDIATE for writers.

    A deferred transaction that reads and then writes fails at once with SQLITE_BUSY when another
    writer committed in between; BEGIN IMMEDIATE takes the write lock up front and waits for it
    (busy_timeout) instead, so concurrent writers queue up.
    """
    # check_same_thread is off because FastAPI runs sync endpoints in a thread pool.
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _on_connect)
    begin = "BEGIN IMMEDIATE" if immediate else "BEGIN"

    def _begin(conn: Connection) -> None:
        conn.exec_driver_sql(begin)

    event.listen(engine, "begin", _begin)
    return engine


class Database:
    def __init__(self, path: Path) -> None:
        self.read_engine = make_engine(path)
        self.write_engine = make_engine(path, immediate=True)
        self.reader = sessionmaker(bind=self.read_engine, expire_on_commit=False)
        self.writer = sessionmaker(bind=self.write_engine, expire_on_commit=False)

    def dispose(self) -> None:
        self.read_engine.dispose()
        self.write_engine.dispose()


_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_session(request: Request) -> Iterator[Session]:
    db: Database = request.app.state.db
    factory = db.reader if request.method in _READ_METHODS else db.writer
    with factory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]
