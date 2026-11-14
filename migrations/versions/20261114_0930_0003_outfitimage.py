"""rename generatedimage -> outfitimage

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14

``GeneratedImage`` was dead code (0 rows, 0 readers) and its column set was wrong for what
it was meant to record, so this is a DROP + CREATE rather than a rename:

    dropped: prompt, and the nullable outfit_id
    added:   view (free text), model (provenance), NOT NULL outfit_id

The new table is ``outfitimage``: one row per model view per outfit.

* ``UNIQUE(outfit_id, view)`` — guards against a retry or double-submit silently writing a
  second ``center`` image for the same outfit. Ordering is NOT stored; the frontend orders
  views against ``settings.model_image_views``, so ``view`` is free text and adding one
  needs no migration.
* ``outfit_id`` is NOT NULL — an outfit image with no outfit is a contradiction.
* ``model`` is kept because ``settings.image_model_tryon`` changes over time, so the model
  that rendered a row cannot be re-derived later.
* indexes on ``user_id`` and ``outfit_id`` for the history and per-outfit queries.

No data migration: the old table was empty. Verified with ``SELECT count(*) FROM
generatedimage`` -> 0 before writing this.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """rename generatedimage -> outfitimage"""
    op.drop_table("generatedimage")
    op.create_table(
        "outfitimage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("outfit_id", sa.Uuid(), nullable=False),
        sa.Column("view", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("image_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["outfit_id"], ["outfit.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outfit_id", "view", name="uq_outfitimage_outfit_view"),
    )
    op.create_index("ix_outfitimage_user_id", "outfitimage", ["user_id"])
    op.create_index("ix_outfitimage_outfit_id", "outfitimage", ["outfit_id"])


def downgrade() -> None:
    """rename generatedimage -> outfitimage"""
    op.drop_index("ix_outfitimage_outfit_id", table_name="outfitimage")
    op.drop_index("ix_outfitimage_user_id", table_name="outfitimage")
    op.drop_table("outfitimage")
    op.create_table(
        "generatedimage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("outfit_id", sa.Uuid(), nullable=True),
        sa.Column("prompt", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("image_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["outfit_id"], ["outfit.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )