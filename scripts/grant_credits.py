"""Grant credits to the local user.

Run with ``make credits N=10`` or ``uv run python scripts/grant_credits.py --amount 10``.

Every grant is recorded in ``creditledger``, so a top-up is auditable rather than a
silent edit to the balance column.
"""

import argparse

from sqlmodel import Session, select

from closet_muse.db.engine import engine
from closet_muse.db.models import User
from closet_muse.services import credits


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant credits to the local user.")
    parser.add_argument(
        "--amount",
        type=int,
        default=10,
        help="Credits to add (must be positive). Default: 10.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="User to credit. Default: 1 (the single local user).",
    )
    args = parser.parse_args()

    with Session(engine) as session:
        user = session.get(User, args.user_id)
        if user is None:
            # Do not create a user here: seeding is ``make seed``'s job, and a silent
            # create would hide a wrong --user-id.
            raise SystemExit(f"User {args.user_id} not found. Run `make seed` first.")

        before = user.credits
        after = credits.grant(
            session, args.user_id, args.amount, credits.REASON_MANUAL_TOPUP
        )
        session.commit()

    print(f"User {args.user_id}: {before} -> {after} credits (+{args.amount}).")


if __name__ == "__main__":
    main()
