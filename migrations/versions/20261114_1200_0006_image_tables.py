"""clothing image tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-14

Moves a garment's images out of two columns on ``clothing`` and into two child tables.
They are deliberately **two** tables rather than one with a ``kind`` discriminator: the
two kinds have different shapes (``view`` vs ``position``) and different lifecycles, and
a discriminator would force every query to filter on it.

* ``clothing_image`` — the polished mannequin renders. One row per view, so a third view
  needs no schema change. ``UNIQUE(clothing_id, view)`` keeps one render per view per
  item. ``view`` is free text mirroring ``image_generation.MANNEQUIN_VIEWS``.
* ``clothing_source_image`` — the user's original upload photos. These used to be read
  into memory, sent to the image model, and dropped, so the only copy was lost and an
  item could never be re-polished. ``position`` preserves upload order (``0`` = primary).

All four steps run in one revision, in this order, on purpose:

1. create ``clothing_image``
2. create ``clothing_source_image``
3. backfill ``clothing_image`` from ``clothing.image_path`` / ``image_path_tilted``
4. batch-drop both legacy columns

Doing the backfill here (rather than in a separate script) removes the ordering footgun
the old plan had: the columns cannot be dropped before the data is copied, and there is
no way to run the backfill after they are gone. Batch mode is what makes step 4 possible
at all — raw SQLite cannot ``DROP COLUMN``.

No ``copy_from`` is needed for the drop: no column changes type, so Alembic's row copy
stays a plain ``INSERT ... SELECT`` and cannot hit the ``CAST(x AS DATE)`` hazard that
revision ``0004`` had to work around.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """clothing image tables"""
    op.create_table(
        "clothing_image",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clothing_id", sa.Uuid(), nullable=False),
        sa.Column("view", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("image_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clothing_id"], ["clothing.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clothing_id", "view", name="uq_clothingimage_clothing_view"),
    )
    op.create_index("ix_clothingimage_clothing_id", "clothing_image", ["clothing_id"])

    op.create_table(
        "clothing_source_image",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clothing_id", sa.Uuid(), nullable=False),
        sa.Column("image_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clothing_id"], ["clothing.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_clothingsourceimage_clothing_id", "clothing_source_image", ["clothing_id"]
    )

    # Backfill the polished views. ``clothing.id`` is stored dashless (CHAR(32)), so the
    # generated ids must be dashless too — ``hex(randomblob(16))`` yields exactly that.
    # ``created_at`` is inherited from the garment: the render predates this table, so
    # the item's own timestamp is the closest honest value.
    for column, view in (("image_path", "front"), ("image_path_tilted", "tilted")):
        op.execute(
            f"""
            INSERT INTO clothing_image (id, clothing_id, view, image_path, created_at)
            SELECT lower(hex(randomblob(16))), id, '{view}', {column}, created_at
            FROM clothing
            WHERE {column} IS NOT NULL AND {column} != ''
            """
        )

    # Now that every path is copied, the legacy columns can go. Batch mode performs the
    # create-copy-drop-rename rebuild SQLite needs for DROP COLUMN.
    with op.batch_alter_table("clothing") as batch_op:
        batch_op.drop_column("image_path_tilted")
        batch_op.drop_column("image_path")


def downgrade() -> None:
    """clothing image tables"""
    # Re-add the two columns, then copy the polished views back. ``front`` is the only
    # required one; ``tilted`` stays nullable, matching the pre-0006 shape.
    with op.batch_alter_table("clothing") as batch_op:
        batch_op.add_column(
            sa.Column("image_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "image_path_tilted", sqlmodel.sql.sqltypes.AutoString(), nullable=True
            )
        )

    op.execute(
        """
        UPDATE clothing
        SET image_path = (
            SELECT image_path FROM clothing_image
            WHERE clothing_image.clothing_id = clothing.id AND view = 'front'
        )
        """
    )
    op.execute(
        """
        UPDATE clothing
        SET image_path_tilted = (
            SELECT image_path FROM clothing_image
            WHERE clothing_image.clothing_id = clothing.id AND view = 'tilted'
        )
        """
    )

    op.drop_index("ix_clothingsourceimage_clothing_id", table_name="clothing_source_image")
    op.drop_table("clothing_source_image")
    op.drop_index("ix_clothingimage_clothing_id", table_name="clothing_image")
    op.drop_table("clothing_image")
