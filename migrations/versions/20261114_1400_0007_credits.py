"""credits balance and ledger

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-14

Adds a spendable credit balance to the single local user, plus an append-only ledger
recording every movement.

* ``user.credits`` — the balance. Kept on the row so reading it is one lookup rather
  than an aggregate over the ledger.
* ``creditledger`` — one row per spend/grant. ``balance_after`` is stored, not derived,
  because the ledger is append-only: a later grant must not change what an earlier row
  reported. ``outfit_id`` is nullable (grants are not tied to an outfit) and
  ``ON DELETE SET NULL`` (deleting an outfit must not erase the record that credits
  were spent on it).

**The ``user`` rebuild is the dangerous part.** ``credits`` is added with a
``server_default`` so the existing row gets a value, then a follow-up ``alter_column``
removes that default so the column matches the model (which supplies ``20`` in Python).
SQLite cannot ``ALTER COLUMN``, so batch mode rewrites the whole table — and ``user``
holds ``dob``, a ``DATE``. Alembic emits ``CAST(user.dob AS DATE)`` whenever the target
type differs from the source, and SQLite's ``DATE`` cast has NUMERIC affinity, so
``'1995-01-01'`` silently becomes the integer ``1995``. ``copy_from`` declares ``dob``
with its *post-migration* type (``sa.Date``) so the copy stays a plain
``INSERT ... SELECT`` with no cast. See revision ``0004`` for the original incident.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The starting balance for the existing (and any future) user row.
_INITIAL_CREDITS = 20

# Must match ``services.credits.REASON_INITIAL_GRANT``. Duplicated rather than imported
# because a migration must keep working even if the service module is later refactored.
REASON_INITIAL_GRANT = "initial_grant"


def _user_copy_source(*, with_credits: bool) -> sa.Table:
    """The ``user`` shape batch mode needs as its ``copy_from`` source.

    ``dob`` is declared as ``sa.Date`` — its post-migration type — so the row copy is a
    plain ``INSERT ... SELECT``. Declaring it as ``DateTime`` would make Alembic emit
    ``CAST(user.dob AS DATE)``, which mangles the date into an integer (see the module
    docstring).

    ``with_credits`` must match whether the live table has the column at the point the
    batch runs, because ``copy_from`` describes the table being copied *from*.
    """
    columns = [
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("dob", sa.Date(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]
    if with_credits:
        columns.append(sa.Column("credits", sa.Integer(), nullable=False))
    return sa.Table("user", sa.MetaData(), *columns)


def upgrade() -> None:
    """credits balance and ledger"""
    op.create_table(
        "creditledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("outfit_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outfit_id"], ["outfit.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("creditledger") as batch_op:
        batch_op.create_index("ix_creditledger_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_creditledger_outfit_id", ["outfit_id"], unique=False)

    # A bare ADD COLUMN needs no rebuild, so it cannot disturb ``dob``.
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column(
                "credits",
                sa.Integer(),
                nullable=False,
                server_default=sa.text(str(_INITIAL_CREDITS)),
            )
        )
    # Now rebuild once to drop the temporary server default. See ``_user_copy_source``
    # for why copy_from is mandatory here.
    with op.batch_alter_table(
        "user", copy_from=_user_copy_source(with_credits=True), recreate="always"
    ) as batch_op:
        batch_op.alter_column(
            "credits",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default=None,
        )

    # Record the starting balance as a ledger row, so the ledger is COMPLETE: summing
    # ``delta`` must always reproduce ``user.credits``. Without this the opening balance
    # would be invisible to the audit trail and the two would disagree by exactly the
    # initial grant. Runs after the rebuild so the ``user`` rows are final.
    op.execute(
        f"""
        INSERT INTO creditledger (id, user_id, delta, reason, balance_after, outfit_id, created_at)
        SELECT lower(hex(randomblob(16))), id, credits, '{REASON_INITIAL_GRANT}', credits, NULL, CURRENT_TIMESTAMP
        FROM user
        """
    )


def downgrade() -> None:
    """credits balance and ledger"""
    # ``copy_from`` describes the table being copied FROM, so it still has ``credits``.
    with op.batch_alter_table(
        "user", copy_from=_user_copy_source(with_credits=True), recreate="always"
    ) as batch_op:
        batch_op.drop_column("credits")

    op.drop_table("creditledger")
