"""Local filesystem-backed image storage.

Replaces the previous remote object store: images are written under
``settings.storage_dir/<bucket>/``. Stored ``image_path`` values are simply the
generated filename; the bucket is implied by the owning record.
"""

import uuid
from pathlib import Path

from closet_muse.settings import settings


def bucket_dir(bucket: str) -> Path:
    path = Path(settings.storage_dir) / bucket
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_image(bucket: str, data: bytes, *, ext: str = "png") -> str:
    """Write ``data`` to ``<bucket>/<uuid>.<ext>`` and return the filename."""
    filename = f"{uuid.uuid4()}.{ext}"
    (bucket_dir(bucket) / filename).write_bytes(data)
    return filename


def image_path(bucket: str, filename: str) -> Path:
    """Resolve a stored filename to a path within its bucket (traversal-safe)."""
    if Path(filename).name != filename or filename in {"", ".", ".."}:
        raise ValueError(f"Invalid image path: {filename!r}")
    return bucket_dir(bucket) / filename


def read_image(bucket: str, filename: str) -> bytes:
    return image_path(bucket, filename).read_bytes()


def delete_image(bucket: str, filename: str) -> None:
    """Delete a stored image; a missing file (or invalid name) is not an error."""
    try:
        image_path(bucket, filename).unlink()
    except (ValueError, FileNotFoundError):
        pass

