"""Reclaim image files that no database row points at.

Every stored image is written as ``<storage_dir>/<bucket>/<uuid>.<ext>`` and the owning
row keeps only the bare filename (the bucket is implied by which table the row is in).
That means an image is live exactly when some row in the matching table references its
filename. Anything else in the bucket is an orphan:

* renders written before outfit persistence existed (the try-on flow used to discard the
  filename returned by ``storage.save_image``), and
* files left behind by a crashed write.

Both are unreachable through the API, so they are pure dead weight.

Safety properties, in order of importance:

* **Dry run by default.** Nothing is deleted unless ``--apply`` is passed.
* **Only ``var/storage/<bucket>/`` is scanned.** ``assets/`` is never touched; it holds
  hand-made inputs and generated models that are not tracked by any table.
* **A missing bucket directory is skipped, never created.** ``storage.bucket_dir()``
  creates directories as a side effect, so this script deliberately resolves paths itself.
* **A bucket whose table is missing or unreadable is skipped with a warning.** A database
  that has not been migrated (or a mistyped ``SQLITE_PATH``) must never be interpreted as
  "every file is an orphan" — that would delete the entire wardrobe.

Buckets and the columns that own them are declared in ``BUCKET_SOURCES``. Revision ``0006``
moved the polished clothing images into ``clothing_image`` and added the
``clothing_source`` bucket for the user's original uploads; both are listed there.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from closet_muse.settings import settings


@dataclass(frozen=True)
class BucketSource:
    """A storage bucket and the (table, column) pairs whose rows own its files."""

    bucket: str
    # Every column that can hold a filename in this bucket. A file is live if it
    # matches a value in ANY of these columns.
    sources: tuple[tuple[str, str], ...]


# The ModelView / clothing / avatar buckets, matching ``settings``.
BUCKET_SOURCES: tuple[BucketSource, ...] = (
    BucketSource(
        bucket=settings.storage_bucket_generated,
        sources=(("outfitimage", "image_path"),),
    ),
    BucketSource(
        bucket=settings.storage_bucket_clothing,
        sources=(("clothing_image", "image_path"),),
    ),
    BucketSource(
        bucket=settings.storage_bucket_clothing_source,
        sources=(("clothing_source_image", "image_path"),),
    ),
    BucketSource(
        bucket=settings.storage_bucket_avatar,
        sources=(("avatarimage", "image_path"),),
    ),
)


def _referenced_filenames(
    connection: sqlite3.Connection, source: BucketSource
) -> set[str] | None:
    """Return every filename the database says is live in ``source.bucket``.

    ``None`` means "cannot tell" — the table or column is missing, which happens on an
    unmigrated database. Callers must skip the bucket rather than treat its files as
    orphans, because deleting on uncertainty destroys user photos.
    """
    names: set[str] = set()
    for table, column in source.sources:
        try:
            rows: Iterable[tuple[object]] = connection.execute(
                f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL"  # noqa: S608
            ).fetchall()
        except sqlite3.Error:
            return None
        names.update(str(value) for (value,) in rows if value)
    return names


def _scan_bucket(
    connection: sqlite3.Connection, source: BucketSource
) -> tuple[list[Path], bool]:
    """Return ``(orphaned files, could_check)`` for one bucket."""
    directory = Path(settings.storage_dir) / source.bucket
    if not directory.is_dir():
        return [], True

    referenced = _referenced_filenames(connection, source)
    if referenced is None:
        return [], False

    orphans = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.name not in referenced
    )
    return orphans, True


def _human_size(total_bytes: int) -> str:
    size = float(total_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Delete image files that no database row references. "
            "Dry run unless --apply is given."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete the orphans. Without this the script only reports them.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only (this is already the default; kept for explicitness).",
    )
    args = parser.parse_args(argv)

    # ``--apply`` wins over ``--dry-run`` only by convention; passing both is a mistake.
    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run are mutually exclusive.")

    db_path = Path(settings.sqlite_path)
    if not db_path.exists():
        print(f"error: database not found at {db_path}", file=sys.stderr)
        return 1

    connection = sqlite3.connect(db_path)
    try:
        total = 0
        for source in BUCKET_SOURCES:
            orphans, could_check = _scan_bucket(connection, source)
            if not could_check:
                print(
                    f"! {source.bucket}: table/column missing in the database; "
                    "skipping this bucket entirely",
                    file=sys.stderr,
                )
                continue
            if not orphans:
                print(f"{source.bucket}: no orphans")
                continue

            size = _human_size(sum(path.stat().st_size for path in orphans))
            verb = "deleted" if args.apply else "would delete"
            print(f"{source.bucket}: {verb} {len(orphans)} orphan(s), {size}")
            for path in orphans:
                print(f"  - {source.bucket}/{path.name}")
                if args.apply:
                    path.unlink()
            total += len(orphans)
    finally:
        connection.close()

    if total and not args.apply:
        print(f"\n{total} orphan(s) found. Re-run with --apply to delete them.")
    elif total:
        print(f"\n{total} orphan(s) deleted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
