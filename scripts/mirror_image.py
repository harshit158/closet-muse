"""Mirror an image - flip it like a reflection in a mirror.

By default the image is flipped horizontally (left <-> right), which is what a
mirror does. Pass ``--axis vertical`` to flip top <-> bottom instead.

The EXIF orientation tag is applied before flipping and is not carried over to
the output, so a rotated phone photo is mirrored the way it looks on screen
rather than the way its raw pixels are stored.

The mirrored image is written next to the input with a ``_mirrored`` suffix
unless ``--output`` is given.

Examples
--------
Mirror an image in place (writes ``assets/avatar/model_generated_mirrored.png``)::

    uv run python scripts/mirror_image.py assets/avatar/model_generated.png

Mirror to an explicit path::

    uv run python scripts/mirror_image.py photo.jpg --output photo_flipped.jpg

Flip top to bottom instead of left to right::

    uv run python scripts/mirror_image.py photo.jpg --axis vertical

Overwrite an existing output::

    uv run python scripts/mirror_image.py photo.jpg --overwrite
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

# Suffix appended to the input stem to derive the default output path.
MIRRORED_SUFFIX = "_mirrored"


def _mirrored_path(source: Path) -> Path:
    """Return the default output path derived from the input path.

    ``assets/avatar/model_generated.png`` -> ``assets/avatar/model_generated_mirrored.png``.
    """
    return source.with_name(f"{source.stem}{MIRRORED_SUFFIX}{source.suffix}")


def mirror(source: Path, axis: str) -> Image.Image:
    """Open ``source`` and return it flipped along ``axis`` ("horizontal"/"vertical").

    The EXIF orientation tag is baked into the pixels first (and dropped from the
    result) so the flip matches what the user sees.
    """
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img) or img
        if axis == "horizontal":
            return ImageOps.mirror(img)
        return ImageOps.flip(img)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mirror an image (flip it like a reflection).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="Path to the image to mirror.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Path to write the mirrored image to. Defaults to the input path with a "
            "'_mirrored' suffix."
        ),
    )
    parser.add_argument(
        "--axis",
        choices=["horizontal", "vertical"],
        default="horizontal",
        help="Flip left<->right (horizontal, a mirror) or top<->bottom (vertical).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    source = args.input
    if not source.is_file():
        print(f"error: input image not found: {source}", file=sys.stderr)
        return 2

    output = args.output or _mirrored_path(source)
    if output.exists() and not args.overwrite:
        print(f"skip  {output} (exists; use --overwrite)")
        return 0

    try:
        image = mirror(source, args.axis)
    except Exception as exc:  # noqa: BLE001 - surface any failure to the user
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print(f"flip  {args.axis} {source} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
