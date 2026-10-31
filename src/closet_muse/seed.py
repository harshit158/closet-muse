"""Seed script: create a local user in the SQLite database.

Run with ``make seed`` or ``uv run python -m closet_muse.seed``.
"""

import datetime

from sqlmodel import Session, select

from closet_muse.db.engine import create_db_and_tables, engine
from closet_muse.db.models import User


def main() -> None:
    create_db_and_tables()

    with Session(engine) as session:
        existing = session.exec(select(User)).first()
        if existing is not None:
            print(f"User already exists: id={existing.id}, name={existing.name!r}")
            return

        user = User(
            name="Local User",
            dob=datetime.datetime(1995, 1, 1, tzinfo=datetime.timezone.utc),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"Created user: id={user.id}, name={user.name!r}")


if __name__ == "__main__":
    main()
