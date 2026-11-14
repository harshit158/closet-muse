"""Credit accounting for paid image generation.

The balance lives on ``user.credits``; every movement is also appended to
``creditledger``. This module is the **only** place a balance is mutated, so the two
can never drift apart.

Transactions are the caller's responsibility: :func:`spend` and :func:`grant` flush but
never commit. That lets a spend be rolled back together with the work it paid for — a
failed outfit save must not leave the user charged for an image that was never stored.
"""

from sqlalchemy import update
from sqlmodel import Session

from closet_muse.db import models

# What one outfit generation costs. A flat cost per user-visible action, not per
# underlying API call: the try-on makes one request per model view, but the user asked
# for one look, so it is charged once. A module constant rather than a ``Settings``
# field because a price is a product decision, not deployment configuration.
CREDIT_COST_OUTFIT = 1

# Credits a brand-new user starts with. Applied through :func:`grant` (never a column
# default) so the opening balance is recorded in the ledger like every other movement.
INITIAL_GRANT = 20

# Ledger ``reason`` values. Free text in the database (adding one needs no migration),
# but centralised here so the strings cannot drift between call sites.
REASON_OUTFIT_GENERATION = "outfit_generation"
REASON_INITIAL_GRANT = "initial_grant"
REASON_MANUAL_TOPUP = "manual_topup"


class InsufficientCredits(Exception):
    """Raised when a spend would take the balance below zero."""

    def __init__(self, balance: int, required: int) -> None:
        self.balance = balance
        self.required = required
        super().__init__(
            f"Insufficient credits: {balance} available, {required} required."
        )


def get_balance(session: Session, user_id: int) -> int:
    """Return a user's current balance.

    Raises ``LookupError`` when the user does not exist, so a caller cannot silently
    treat a missing user as a zero balance.
    """
    user = session.get(models.User, user_id)
    if user is None:
        raise LookupError(f"User {user_id} not found.")
    return user.credits


def spend(
    session: Session,
    user_id: int,
    amount: int,
    reason: str,
    *,
    outfit_id=None,
) -> int:
    """Deduct ``amount`` credits and record the movement; return the new balance.

    The deduction is a single conditional ``UPDATE``, so the balance check and the
    write cannot be separated by another transaction — a read-then-write would let two
    concurrent requests both pass the check and overdraw the account.

    Raises :class:`InsufficientCredits` when the balance is too low. Does **not**
    commit: the caller owns the transaction, so a failure later in the same unit of
    work rolls the deduction back.
    """
    if amount <= 0:
        raise ValueError(f"Spend amount must be positive, got {amount}.")

    result = session.execute(
        update(models.User)
        .where(models.User.id == user_id, models.User.credits >= amount)
        .values(credits=models.User.credits - amount)
    )
    if result.rowcount == 0:
        # Either the user is missing or the balance is too low; distinguish them so a
        # caller bug is not reported as an empty wallet.
        user = session.get(models.User, user_id)
        if user is None:
            raise LookupError(f"User {user_id} not found.")
        raise InsufficientCredits(balance=user.credits, required=amount)

    # Re-read so ``balance_after`` is the value the database actually holds. The
    # identity map may still carry the pre-update object, so expire just that row
    # rather than the whole session (which would discard the caller's pending work).
    session.expire(session.get(models.User, user_id))
    balance = session.get(models.User, user_id).credits

    session.add(
        models.CreditLedger(
            user_id=user_id,
            delta=-amount,
            reason=reason,
            balance_after=balance,
            outfit_id=outfit_id,
        )
    )
    session.flush()
    return balance


def grant(session: Session, user_id: int, amount: int, reason: str) -> int:
    """Add ``amount`` credits and record the movement; return the new balance.

    Used by the seed script and the manual top-up helper. Does not commit.
    """
    if amount <= 0:
        raise ValueError(f"Grant amount must be positive, got {amount}.")

    user = session.get(models.User, user_id)
    if user is None:
        raise LookupError(f"User {user_id} not found.")

    user.credits += amount
    session.add(user)
    session.flush()

    session.add(
        models.CreditLedger(
            user_id=user_id,
            delta=amount,
            reason=reason,
            balance_after=user.credits,
        )
    )
    session.flush()
    return user.credits
