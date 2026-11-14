"""Alembic migration script template.

Generated revisions inherit from this; ``upgrade()`` / ``downgrade()`` are filled in by
``alembic revision --autogenerate`` (or by hand).

``repr()`` is used for the revision identifiers so a missing parent renders as the Python
literal ``None`` rather than the string ``"None"`` — the latter breaks Alembic's revision
map with ``KeyError: 'None'``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    """${message}"""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """${message}"""
    ${downgrades if downgrades else "pass"}
