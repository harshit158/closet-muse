"""drop dead tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-14

Removes two tables that never received a row (verified immediately before writing this:
``SELECT count(*)`` -> 0 on both) and whose code paths were unreachable:

* ``surpriseoutfit`` — the "Surprise Me" feature's storage. Its only consumer was a
  literal ``pass`` stub, and no endpoint ever wrote one. The one field worth keeping,
  ``feedback``, already moved to ``outfit`` in revision ``0004``.
* ``bodyprofile`` — body measurements, superseded by the generated model images in
  ``assets/avatar/`` + ``settings.model_image_views``. The only writer updated an
  existing row *if one existed*, and no endpoint ever created one.

No data migration: both tables are empty, so a plain DROP loses nothing.

``downgrade()`` recreates both tables exactly as ``0001_baseline`` declared them, so
``make downgrade`` restores the pre-``0005`` shape. The recreation is only structural —
there are no rows to restore, which is why the downgrade cannot lose data either.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """drop dead tables"""
    op.drop_table("surpriseoutfit")
    op.drop_table("bodyprofile")


def downgrade() -> None:
    """drop dead tables"""
    # Shapes copied from ``0001_baseline`` so a full downgrade chain rebuilds the
    # exact schema ``0004`` left behind.
    op.create_table(
        "bodyprofile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("skin_tone", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("body_shape", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("avatar_image_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "surpriseoutfit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("outfit_id", sa.Uuid(), nullable=False),
        sa.Column(
            "surprise_prompt", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("feedback", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["outfit_id"], ["outfit.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
