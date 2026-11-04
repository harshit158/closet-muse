"""Generate the reusable fashion-model image used as the virtual try-on subject.

The script builds one photorealistic model image from a set of reference
photographs of the *same* person (for example a front photo, a three-quarter
shot, and a face close-up). Every reference is attached to the request so the
model can read the person's identity - face, hair, skin tone, and body
proportions - from all angles and reproduce it consistently.

The output is a single polished full-body studio fashion-model photograph of that
person, wearing the exact same outfit as the reference, standing straight-on from
head to feet on a plain seamless studio background. No reference photo appears in
the output.

The generated image is written to a single file (``assets/avatar/model_generated.png``
by default) and is meant to be used the same way as the existing
``assets/avatar/model.jpg``: as the subject photo for virtual try-on.

Examples
--------
Generate from the default single reference (skips if the output exists)::

    uv run python scripts/generate_model.py

Generate from several references of the same person::

    uv run python scripts/generate_model.py \\
        --reference-image photo_front.jpg photo_side.jpg face.jpg \\
        --output assets/avatar/model_generated.png

Force a regeneration even if the output already exists::

    uv run python scripts/generate_model.py --overwrite

The OpenRouter API key is read from the ``OPENROUTER_API_KEY`` environment
variable (``.env`` is loaded automatically if present) or from ``--api-key``.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageOps

try:  # optional convenience: load a local .env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:  # pragma: no cover - dotenv is a project dependency
    pass

API_URL = "https://openrouter.ai/api/v1/images"
DEFAULT_MODEL = "meta/muse-image"
DEFAULT_REFERENCE_IMAGES = ["assets/sample_top.JPG"]
DEFAULT_OUTPUT = "assets/avatar/model_generated.png"
# Single full-body portrait output.
DEFAULT_ASPECT_RATIO = "2:3"
DEFAULT_SEED = 42
DEFAULT_TIMEOUT = 180
# References are downscaled and JPEG-encoded before base64 encoding: large
# uncompressed uploads are dropped mid-TLS by OpenRouter (SSLEOFError).
# Set ``--max-dimension 0`` to send the references untouched.
DEFAULT_MAX_DIMENSION = 1024
DEFAULT_JPEG_QUALITY = 85

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

PROMPT_MODEL_TEMPLATE = """
Using the uploaded reference photograph of a person, create a single polished full-body studio fashion-model photograph of that same person. Do not include the reference photograph, a comparison, a collage, a split panel, or any second image in the output - the result must be one single image of the person on their own.{reference_guidance}

OBJECTIVE:
Produce one clean, polished, full-body studio fashion-model photograph of the person from the reference, for use as the subject reference in virtual clothing try-on. It must look like a real editorial studio photo of that exact person, not a comparison or a composite.

1. SUBJECT
* The same individual as the reference: identical face, facial features, hair color and style, skin tone, and overall appearance.
* A photorealistic editorial fashion model: a real-looking person, not a mannequin and not a drawing.
* Do not idealize, slim, reshape, age, or restyle the person, and do not substitute a different-looking person.

2. FRAMING
* Straight-on front view of the whole person, from the top of the head down to the feet.
* Centered in the frame with a small even margin of empty background around the person.
* One image only: no side-by-side, no before/after, no reference photo in frame, no divider.

3. POSE
* Simple upright, neutral standing posture.
* Arms held relaxed and slightly away from the sides.
* Legs straight with a small natural gap; feet facing forward.
* Static and relaxed; no bending or twisting.

4. WARDROBE AND STYLING
* The person must wear the exact same clothing and outfit shown in the reference photograph. Reproduce every garment worn in the reference.
* Reproduce each garment's exact design: color, fabric, pattern, texture, seams, stitching, hardware, and any logos or prints.
* Do not substitute, restyle, recolor, redesign, or omit any garment from the reference.
* Do not add any garment, layer, or accessory that is not in the reference.
* Keep the same layering, fit, and drape as the reference.

5. LIGHTING AND BACKGROUND
* Soft, even studio lighting with minimal shadows.
* Plain, seamless light grey or white background.
* No room, props, or environmental objects; the background is a clean studio backdrop.

6. OUTPUT QUALITY
* High-resolution, polished, retouched studio-quality image with a clean silhouette.
* The person's identity, features, and outfit are clearly recognizable and faithful to the reference.
* Suitable as a reusable subject reference for virtual clothing try-on.

IMPORTANT:
Output exactly one polished full-body studio photograph of the person.
Do NOT include the reference photograph, a comparison, a collage, a split panel, a divider, or a second image.
The person must match the reference exactly in identity, facial features, and outfit.
"""

# Added when more than one reference photo is supplied (a primary shot plus
# additional angles or a face close-up) so the model reads them as one person.
MULTI_REFERENCE_GUIDANCE = (
    "\n\nThe person appears in several uploaded photographs: a primary shot plus "
    "additional angles or a face close-up. Treat every photograph as the same single "
    "person and use them together to read the person's exact identity, hair, skin tone, "
    "body proportions, and outfit. If the photographs disagree on a detail, prefer the primary "
    "photograph for overall build, outfit, and framing and the close-ups for facial features."
)


def _load_reference(path: Path, max_dimension: int) -> Image.Image:
    """Open a reference photo as RGB with EXIF orientation applied.

    Re-encoding an image drops its EXIF orientation tag, so the rotation has to
    be baked into the pixels here; otherwise a rotated phone photo is sent (and
    reproduced) sideways. The image is downscaled so its longest side is at most
    ``max_dimension`` unless ``max_dimension <= 0``.
    """
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img) or img
        img = img.convert("RGB")
    if max_dimension > 0:
        width, height = img.size
        longest = max(width, height)
        if longest > max_dimension:
            scale = max_dimension / longest
            img = img.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.Resampling.LANCZOS,
            )
    return img


def _to_data_url(data: bytes, mime: str | None = None) -> str:
    """Return a ``data:`` URL for the given image bytes."""
    mime = mime or "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _reference_data_url(path: Path, max_dimension: int, quality: int) -> str:
    """Return a ``data:`` URL for a reference photo (orientation-corrected)."""
    img = _load_reference(path, max_dimension)
    out = BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return _to_data_url(out.getvalue(), "image/jpeg")


def _build_prompt(num_references: int) -> str:
    """Build the model prompt, adding multi-reference guidance when needed."""
    guidance = MULTI_REFERENCE_GUIDANCE if num_references > 1 else ""
    return PROMPT_MODEL_TEMPLATE.format(reference_guidance=guidance)


def _generate(
    *,
    api_key: str,
    model: str,
    prompt: str,
    reference_paths: list[Path],
    aspect_ratio: str,
    seed: int,
    timeout: int,
    max_dimension: int,
    jpeg_quality: int,
) -> bytes:
    """Call the OpenRouter image API and return the generated PNG bytes."""
    for reference_path in reference_paths:
        if not reference_path.is_file():
            raise FileNotFoundError(f"Reference image not found: {reference_path}")

    payload = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "input_references": [
            {
                "type": "image_url",
                "image_url": {
                    "url": _reference_data_url(path, max_dimension, jpeg_quality)
                },
            }
            for path in reference_paths
        ],
        "n": 1,
        "output_format": "png",
        "seed": seed,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(API_URL, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    body = response.json()

    if body.get("error"):
        raise RuntimeError(f"API error: {body['error']}")

    data = body.get("data") or []
    if not data or not data[0].get("b64_json"):
        raise RuntimeError(f"Unexpected API response: {body}")

    return base64.b64decode(data[0]["b64_json"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a reusable fashion-model image from reference photos.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--reference-image",
        type=Path,
        nargs="+",
        default=[Path(p) for p in DEFAULT_REFERENCE_IMAGES],
        help=(
            "One or more photos of the same person. Multiple photos (different "
            "angles or a face close-up) improve identity consistency."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT),
        help="Path where the generated model image is written.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Image model to use.")
    parser.add_argument(
        "--aspect-ratio",
        default=DEFAULT_ASPECT_RATIO,
        help="Output aspect ratio; taller values suit a full-body portrait (e.g. 2:3, 3:4).",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Seed for reproducibility.")
    parser.add_argument(
        "--max-dimension",
        type=int,
        default=DEFAULT_MAX_DIMENSION,
        help=(
            "Downscale each reference so its longest side is at most this many pixels "
            "before uploading (0 sends the originals untouched)."
        ),
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=DEFAULT_JPEG_QUALITY,
        help="JPEG quality (1-100) used when compressing references.",
    )
    parser.add_argument("--api-key", default=None, help="OpenRouter API key (else $OPENROUTER_API_KEY).")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout (seconds).")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate even if the output file already exists.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.output.exists() and not args.overwrite:
        print(f"skip  {args.output} (exists; use --overwrite)")
        return 0

    api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print(
            "error: no API key. Set the OPENROUTER_API_KEY environment variable "
            "or pass --api-key.",
            file=sys.stderr,
        )
        return 2

    references = list(args.reference_image)
    if not references:
        print("error: at least one --reference-image is required.", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    prompt = _build_prompt(len(references))

    print(f"gen   references={len(references)}")
    for reference in references:
        print(f"      {reference}")
    try:
        image_bytes = _generate(
            api_key=api_key,
            model=args.model,
            prompt=prompt,
            reference_paths=references,
            aspect_ratio=args.aspect_ratio,
            seed=args.seed,
            timeout=args.timeout,
            max_dimension=args.max_dimension,
            jpeg_quality=args.jpeg_quality,
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure to the user
        print(f"error: {exc}", file=sys.stderr)
        return 1

    args.output.write_bytes(image_bytes)
    print(f"saved {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
