"""Seed script: create a local user in the SQLite database.

Run with ``make seed`` or ``uv run python -m closet_muse.seed``.

Assumes the schema already exists — run ``make migrate`` first. This script no longer
creates tables; Alembic owns the schema (see ``migrations/env.py``).
"""

import datetime

from sqlmodel import Session, select

from closet_muse.db.engine import engine
from closet_muse.db.models import User
from closet_muse.services import credits


def main() -> None:
    with Session(engine) as session:
        existing = session.exec(select(User)).first()
        if existing is not None:
            print(f"User already exists: id={existing.id}, name={existing.name!r}")
            return

        user = User(
            name="Local User",
            dob=datetime.date(1995, 1, 1),
        )
        session.add(user)
        # Assigns user.id so the ledger row can reference it.
        session.flush()
        # Granted explicitly (not via a column default) so the opening balance is
        # recorded in the ledger and ``sum(delta) == credits`` always holds.
        balance = credits.grant(
            session, user.id, credits.INITIAL_GRANT, credits.REASON_INITIAL_GRANT
        )
        session.commit()
        session.refresh(user)
        print(
            f"Created user: id={user.id}, name={user.name!r}, credits={balance}"
        )


if __name__ == "__main__":
    main()
