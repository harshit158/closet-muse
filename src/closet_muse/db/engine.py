"""SQLite engine and session management.

Uses a local SQLite file (see ``settings.sqlite_path``).

The schema is owned by Alembic, not by ``SQLModel.metadata.create_all()``. Run
``make migrate`` to create or update the database; the application never issues DDL.
See ``migrations/env.py`` and ``scripts/migrate.py``.
"""

from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, create_engine

from closet_muse.settings import settings

# Ensure the parent directory of the database file exists.
_db_path = Path(settings.sqlite_path)
_db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{_db_path}",
    echo=False,
    # Streamlit and FastAPI may touch the session from different threads.
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record) -> None:
    """Apply per-connection SQLite PRAGMAs.

    - ``foreign_keys=ON``: SQLite defaults to OFF, which makes every
      ``REFERENCES`` clause decorative. Enabling it means ``ON DELETE CASCADE``
      and FK violations are actually enforced.
    - ``journal_mode=WAL``: lets Streamlit and FastAPI read while the other
      writes, instead of serialising on a rollback journal.
    - ``busy_timeout=5000``: wait up to 5s for a lock instead of failing
      immediately with ``database is locked``.

    Note: Alembic builds its own engine and deliberately does NOT use this
    listener, because batch-mode table rebuilds require foreign keys to be off.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def get_session() -> Session:
    """Return a new database session."""
    return Session(engine)
