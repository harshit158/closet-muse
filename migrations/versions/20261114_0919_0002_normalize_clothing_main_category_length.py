"""Normalize ``clothing.main_category`` to the model's declared length.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14

The local database was built when ``WomenClothingMainCategory`` had longer member names,
so ``main_category`` is ``VARCHAR(16)``; the current model produces ``VARCHAR(11)``. SQLite
does not enforce ``VARCHAR`` lengths, so this was never a runtime bug — but it made
``alembic check`` report a permanent type diff, which would pollute every future
autogenerate. Batch mode rewrites the table, so the column ends up matching the model.

The revision is a no-op on any database created from the baseline, because those already
have the correct length.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: str | Sequence[str] | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must match ``enums.WomenClothingMainCategory`` exactly.
_MAIN_CATEGORY = sa.Enum(
    "TOPS",
    "BOTTOMS",
    "ONE_PIECE",
    "FOOTWEAR",
    "OUTERWEAR",
    "LOUNGEWEAR",
    "ACCESSORIES",
    name="womenclothingmaincategory",
)


def upgrade() -> None:
    """Normalize clothing.main_category length"""
    with op.batch_alter_table("clothing") as batch_op:
        batch_op.alter_column(
            "main_category",
            existing_type=sa.VARCHAR(length=16),
            type_=_MAIN_CATEGORY,
            existing_nullable=False,
        )


def downgrade() -> None:
    """Normalize clothing.main_category length"""
    with op.batch_alter_table("clothing") as batch_op:
        batch_op.alter_column(
            "main_category",
            existing_type=_MAIN_CATEGORY,
            type_=sa.VARCHAR(length=16),
            existing_nullable=False,
        )
