"""Shared FastAPI dependencies."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from closet_muse.db.engine import get_session


def session_dep() -> Iterator[Session]:
    session = get_session()
    try:
        yield session
    finally:
        # Drop any uncommitted work so a failed request cannot leave the
        # connection holding a write transaction (or a stale identity map).
        # Guards are needed because a handler may have already closed/rolled
        # back the session, and a rollback on a closed session raises.
        try:
            session.rollback()
        except Exception:  # noqa: BLE001 - cleanup must never mask the real error
            pass
        session.close()


SessionDep = Annotated[Session, Depends(session_dep)]
