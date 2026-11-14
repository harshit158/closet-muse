"""Alembic environment.

Two things about this file are load-bearing:

1. **The URL comes from ``settings.sqlite_path``, not ``alembic.ini``.** One source of
   truth for where the database lives.

2. **This module must never import ``closet_muse.db.engine``.** That module registers a
   ``connect`` listener that turns ``PRAGMA foreign_keys=ON``. Alembic's batch mode
   rewrites a table by creating a new table, copying rows, dropping the original and
   renaming — and foreign keys are enforced *during* that copy, so an enabled PRAGMA
   makes the rebuild fail. We therefore build our own plain engine here, which leaves
   SQLite's default (FKs off) in place.
"""

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from closet_muse.settings import settings

# Import the models for their side effect: every table registers on SQLModel.metadata.
# Never import closet_muse.db.engine — see the module docstring.
from closet_muse.db import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Resolve the database URL from application settings.
_db_path = Path(settings.sqlite_path)
_db_path.parent.mkdir(parents=True, exist_ok=True)
config.set_main_option("sqlalchemy.url", f"sqlite:///{_db_path}")

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live connection (emit SQL to stdout)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite cannot ALTER a table in place; batch mode rewrites it instead.
        render_as_batch=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
