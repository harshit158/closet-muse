"""Apply pending Alembic migrations, adopting a pre-Alembic database if needed.

This is the implementation behind ``make migrate``. It exists for one reason: a database
created by the old ``create_all()`` path has the tables but no ``alembic_version`` row,
so ``alembic upgrade head`` would try to replay the baseline revision and fail with
``table user already exists``.

The fix is to detect that case and ``stamp`` the baseline instead — the existing schema
already *is* the baseline, so recording that fact is the correct action, not replaying
the DDL.

Run with ``make migrate`` or ``uv run python scripts/migrate.py``.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from closet_muse.settings import settings

# Revision id of the baseline migration (``migrations/versions/0001_baseline.py``).
BASELINE_REVISION = "0001"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    """Build a Config that works regardless of the caller's working directory."""
    config = Config(str(_PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PROJECT_ROOT / "migrations"))
    return config


def _table_names(db_path: Path) -> set[str]:
    """Return the table names present in the SQLite file (empty set if it is absent)."""
    if not db_path.exists():
        return set()

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    finally:
        connection.close()
    return {name for (name,) in rows}


def main() -> int:
    db_path = Path(settings.sqlite_path)
    tables = _table_names(db_path)
    config = _alembic_config()

    if "alembic_version" not in tables and "user" in tables:
        print(
            f"Existing pre-Alembic database at {db_path}; "
            f"stamping baseline revision {BASELINE_REVISION}."
        )
        command.stamp(config, BASELINE_REVISION)

    command.upgrade(config, "head")
    return 0


if __name__ == "__main__":
    sys.exit(main())
