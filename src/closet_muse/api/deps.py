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
        session.close()


SessionDep = Annotated[Session, Depends(session_dep)]
