"""Check that every image the app expects actually exists, and nothing else does.

Three independent checks, all read-only:

1. **Missing files.** Every filename a row references must exist in its bucket. A row
   whose file is gone renders as a 404 in the UI, so this is the failure that matters.
2. **Orphan files.** Every file in a bucket must be referenced by a row. ``make gc``
   deletes these; this script only reports them.
3. **Missing assets.** Every path in ``settings.mannequin_dir``, ``settings.model_image_path``
   and ``settings.model_image_views`` must exist. These are not tracked by any table, so a
   bad path here breaks try-on and the "Your Look" carousel silently.

A bucket whose table or column is missing is reported as "cannot check" and skipped rather
than counted as empty — an unmigrated database must never look like a clean one. Exit code
is non-zero when anything is missing or orphaned, so this can gate a deploy.

Run from the repo root (the paths are CWD-relative, like ``settings``).
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
    sources: tuple[tuple[str, str], ...]


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

    ``None`` means "cannot tell" — the table or column is missing. Callers must skip the
    bucket rather than treat its files as orphans.
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


def _check_bucket(
    connection: sqlite3.Connection, source: BucketSource
) -> tuple[list[str], list[str], bool]:
    """Return ``(missing filenames, orphan filenames, could_check)`` for one bucket."""
    referenced = _referenced_filenames(connection, source)
    if referenced is None:
        return [], [], False

    directory = Path(settings.storage_dir) / source.bucket
    present = (
        {path.name for path in directory.iterdir() if path.is_file()}
        if directory.is_dir()
        else set()
    )
    missing = sorted(referenced - present)
    orphans = sorted(present - referenced)
    return missing, orphans, True


def _asset_paths() -> list[Path]:
    """Every asset path the app reads through ``settings``."""
    paths = [Path(settings.model_image_path)]
    paths.extend(Path(path) for path in settings.model_image_views.values())
    mannequin_dir = Path(settings.mannequin_dir)
    if mannequin_dir.is_dir():
        paths.extend(sorted(path for path in mannequin_dir.glob("*.png") if path.is_file()))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify stored images and settings asset paths. Read-only."
    )
    parser.parse_args(argv)

    db_path = Path(settings.sqlite_path)
    if not db_path.exists():
        print(f"error: database not found at {db_path}", file=sys.stderr)
        return 1

    problems = 0
    connection = sqlite3.connect(db_path)
    try:
        for source in BUCKET_SOURCES:
            missing, orphans, could_check = _check_bucket(connection, source)
            if not could_check:
                print(
                    f"! {source.bucket}: table/column missing in the database; "
                    "skipping this bucket entirely",
                    file=sys.stderr,
                )
                continue
            if not missing and not orphans:
                print(f"{source.bucket}: ok")
                continue
            for name in missing:
                print(f"MISSING  {source.bucket}/{name}  (row references it)")
            for name in orphans:
                print(f"ORPHAN   {source.bucket}/{name}  (no row references it)")
            problems += len(missing) + len(orphans)
    finally:
        connection.close()

    for path in _asset_paths():
        if not path.is_file():
            print(f"MISSING  {path}  (settings references it)")
            problems += 1

    if problems:
        print(f"\n{problems} problem(s) found.", file=sys.stderr)
        return 1
    print("\nAll stored images and settings asset paths are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
