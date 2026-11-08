"""SQLite engine and session management.

Uses a local SQLite file (see ``settings.sqlite_path``). No remote database
and no schema juggling — SQLite has no schema concept beyond the default.
"""

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

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


def create_db_and_tables() -> None:
    """Create all tables defined by SQLModel metadata.

    ``create_all`` is idempotent: it creates missing tables and leaves existing
    ones (and their rows) untouched. It does NOT add columns to a table that
    already exists, so a new field needs either a fresh database (``make clean``)
    or a one-off ``ALTER TABLE``.
    """
    # Import models so they are registered on SQLModel.metadata before create_all.
    from closet_muse.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Return a new database session."""
    return Session(engine)
