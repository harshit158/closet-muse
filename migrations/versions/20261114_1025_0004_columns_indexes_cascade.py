"""columns, indexes, and cascading links

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-14

Merges db_plan phases 3 (constraints/indexes) and 5 (column extensions) — both are pure
column/index work on the same tables, so splitting them would produce two revisions that
touch ``clothing`` back to back for no review benefit.

Contents:

* ``clothing``    + ``color_hex``, ``fit``, ``mannequin_form``, ``is_archived``, ``updated_at``
* ``outfit``      + ``feedback``, ``updated_at``; ``occasion``/``season`` retyped to enums
* ``user``        + ``updated_at``; ``dob`` retyped ``datetime`` -> ``date``
* ``avatarimage`` + ``created_at``
* ``outfitclothinglink`` rebuilt with ``ON DELETE CASCADE`` on both foreign keys
* every index from phase 3

Data hazards handled here:

* ``user.dob`` — the seeded row holds ``'1995-01-01 00:00:00.000000'``, which SQLAlchemy's
  SQLite ``DATE`` result processor cannot parse. ``UPDATE user SET dob = date(dob)`` must
  run BEFORE the batch alter, not after.

  **This alone is not enough.** Alembic's batch copy emits
  ``CAST(user.dob AS DATE)`` when the target column's type differs from the source, and
  SQLite's ``DATE`` *cast* has NUMERIC affinity — so ``'1995-01-01'`` is silently coerced
  to the integer ``1995``. Passing ``copy_from`` with ``dob`` already declared as
  ``sa.Date`` makes the copy a plain ``INSERT ... SELECT`` with no cast. Do not remove it.
* SQLite refuses ``ADD COLUMN ... NOT NULL`` without a default even on an empty table, so
  every new ``NOT NULL`` timestamp is added with a ``server_default``, backfilled, then
  tightened to match the model exactly (no lingering server default).
* ``outfitclothinglink``'s constraints are unnamed in the live database, so ``copy_from``
  provides an explicitly named source schema for batch mode. ``refresh=False`` is implied by
  ``recreate="always"``; the table has 0 rows today but the rebuild still copies rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from closet_muse.domain import enums

# Revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum types must match the models exactly, or ``alembic check`` reports drift.
_OCCASION = sa.Enum(enums.Occasion, name="occasion")
_SEASON = sa.Enum(enums.Season, name="season")

_NOW = sa.text("CURRENT_TIMESTAMP")


def _user_copy_source(dob_type: type, *, with_updated_at: bool) -> sa.Table:
    """The ``user`` shape batch mode needs as its ``copy_from`` source.

    ``dob_type`` must be the *post-migration* type, not the current one. Alembic emits
    ``CAST(user.dob AS <new type>)`` in the row copy whenever the target column's type
    differs from the source, and SQLite's ``DATE`` *cast* has NUMERIC affinity — so
    ``'1995-01-01'`` silently becomes the integer ``1995`` (and a later upgrade turns it
    into ``'-4707-05-11'``). Declaring the target type here keeps the copy a plain
    ``INSERT ... SELECT`` with no cast, in both directions.

    ``with_updated_at`` must match whether the live table has the column at the point the
    batch runs, because ``copy_from`` describes the table being copied *from*.
    """
    columns = [
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("dob", dob_type, nullable=False),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    ]
    if with_updated_at:
        columns.append(sa.Column("updated_at", sa.DateTime(), nullable=False))
    return sa.Table("user", sa.MetaData(), *columns)


def _link_table(*, cascade: bool) -> sa.Table:
    """The ``outfitclothinglink`` shape batch mode needs as its ``copy_from`` source.

    The live constraints are unnamed, which batch mode cannot address, so this declares
    them explicitly (with names) — in the pre-migration shape when ``cascade=False``.
    """
    ondelete = "CASCADE" if cascade else None
    return sa.Table(
        "outfitclothinglink",
        sa.MetaData(),
        sa.Column("outfit_id", sa.Uuid(), nullable=False),
        sa.Column("clothing_item_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("outfit_id", "clothing_item_id"),
        sa.ForeignKeyConstraint(
            ["outfit_id"],
            ["outfit.id"],
            name="fk_outfitclothinglink_outfit_id_outfit",
            ondelete=ondelete,
        ),
        sa.ForeignKeyConstraint(
            ["clothing_item_id"],
            ["clothing.id"],
            name="fk_outfitclothinglink_clothing_item_id_clothing",
            ondelete=ondelete,
        ),
    )


def upgrade() -> None:
    """columns, indexes, and cascading links"""
    # --- avatarimage ---------------------------------------------------------
    with op.batch_alter_table("avatarimage") as batch_op:
        batch_op.add_column(
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=_NOW)
        )
        batch_op.create_index("ix_avatarimage_user_id", ["user_id"], unique=False)
    # Existing rows (if any) already have a value from the server default; drop it so
    # the column matches the model, which supplies the timestamp in Python.
    with op.batch_alter_table("avatarimage") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=None,
        )

    # --- clothing -----------------------------------------------------------
    with op.batch_alter_table("clothing") as batch_op:
        batch_op.add_column(
            sa.Column("color_hex", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("fit", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("mannequin_form", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=_NOW)
        )
        batch_op.add_column(
            sa.Column(
                "is_archived", sa.Boolean(), nullable=False, server_default=sa.text("0")
            )
        )
        batch_op.create_index("ix_clothing_user_id", ["user_id"], unique=False)
        batch_op.create_index(
            "ix_clothing_user_id_main_category",
            ["user_id", "main_category"],
            unique=False,
        )
    # Backfill: an untouched row's updated_at equals its created_at.
    op.execute("UPDATE clothing SET updated_at = created_at")
    with op.batch_alter_table("clothing") as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            "is_archived",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=None,
        )

    # --- outfit -------------------------------------------------------------
    with op.batch_alter_table("outfit") as batch_op:
        batch_op.add_column(
            sa.Column("feedback", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=_NOW)
        )
        batch_op.create_index("ix_outfit_user_id", ["user_id"], unique=False)
        # Was free text while ``enums.Occasion`` / ``enums.Season`` sat unused. SQLite
        # stores enums as VARCHAR, so this is a length-only change — but it keeps the
        # schema in sync with the model, which is what ``alembic check`` compares.
        batch_op.alter_column(
            "occasion",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            type_=_OCCASION,
            existing_nullable=True,
        )
        batch_op.alter_column(
            "season",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            type_=_SEASON,
            existing_nullable=True,
        )
    op.execute("UPDATE outfit SET updated_at = created_at")
    with op.batch_alter_table("outfit") as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=None,
        )

    # --- outfitclothinglink -------------------------------------------------
    with op.batch_alter_table(
        "outfitclothinglink", copy_from=_link_table(cascade=False), recreate="always"
    ) as batch_op:
        batch_op.drop_constraint("fk_outfitclothinglink_outfit_id_outfit", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_outfitclothinglink_clothing_item_id_clothing", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_outfitclothinglink_outfit_id_outfit",
            "outfit",
            ["outfit_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_outfitclothinglink_clothing_item_id_clothing",
            "clothing",
            ["clothing_item_id"],
            ["id"],
            ondelete="CASCADE",
        )
        # The composite PK covers (outfit_id, clothing_item_id), so the delete path —
        # which filters on clothing_item_id alone — would otherwise full-scan.
        batch_op.create_index(
            "ix_outfitclothinglink_clothing_item_id", ["clothing_item_id"], unique=False
        )

    # --- user ---------------------------------------------------------------
    # MUST run before any rebuild: the seeded row holds
    # '1995-01-01 00:00:00.000000', which the SQLite DATE result processor cannot parse.
    op.execute("UPDATE user SET dob = date(dob)")
    # A bare ADD COLUMN needs no rebuild, so it cannot disturb ``dob``.
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=_NOW)
        )
    # An untouched row's updated_at equals its created_at.
    op.execute("UPDATE user SET updated_at = created_at")
    # Now rebuild once to drop the temporary server default and retype ``dob``.
    # See ``_user_copy_source`` for why copy_from is mandatory here.
    with op.batch_alter_table(
        "user",
        copy_from=_user_copy_source(sa.Date, with_updated_at=True),
        recreate="always",
    ) as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            "dob",
            existing_type=sa.DateTime(),
            type_=sa.Date(),
            existing_nullable=False,
        )


def downgrade() -> None:
    """columns, indexes, and cascading links"""
    with op.batch_alter_table(
        "user",
        copy_from=_user_copy_source(sa.DateTime, with_updated_at=True),
        recreate="always",
    ) as batch_op:
        batch_op.alter_column(
            "dob",
            existing_type=sa.Date(),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.drop_column("updated_at")

    # Drop the index BEFORE the rebuild: ``recreate="always"`` recreates the table from
    # ``copy_from``, which declares no index, so the index is gone by the time a
    # ``drop_index`` inside that same batch block would run.
    with op.batch_alter_table("outfitclothinglink") as batch_op:
        batch_op.drop_index("ix_outfitclothinglink_clothing_item_id")

    with op.batch_alter_table(
        "outfitclothinglink", copy_from=_link_table(cascade=True), recreate="always"
    ) as batch_op:
        batch_op.drop_constraint("fk_outfitclothinglink_outfit_id_outfit", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_outfitclothinglink_clothing_item_id_clothing", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_outfitclothinglink_outfit_id_outfit", "outfit", ["outfit_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_outfitclothinglink_clothing_item_id_clothing",
            "clothing",
            ["clothing_item_id"],
            ["id"],
        )

    with op.batch_alter_table("outfit") as batch_op:
        batch_op.alter_column(
            "season",
            existing_type=_SEASON,
            type_=sqlmodel.sql.sqltypes.AutoString(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "occasion",
            existing_type=_OCCASION,
            type_=sqlmodel.sql.sqltypes.AutoString(),
            existing_nullable=True,
        )
        batch_op.drop_index("ix_outfit_user_id")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("feedback")

    with op.batch_alter_table("clothing") as batch_op:
        batch_op.drop_index("ix_clothing_user_id_main_category")
        batch_op.drop_index("ix_clothing_user_id")
        batch_op.drop_column("is_archived")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("mannequin_form")
        batch_op.drop_column("fit")
        batch_op.drop_column("color_hex")

    with op.batch_alter_table("avatarimage") as batch_op:
        batch_op.drop_index("ix_avatarimage_user_id")
        batch_op.drop_column("created_at")