"""Generate the reusable fashion-model image used as the virtual try-on subject.

The script builds one photorealistic model image from a set of reference
photographs of the *same* person (for example a front photo, a three-quarter
shot, and a face close-up). Every reference is attached to the request so the
model can read the person's identity - face, hair, skin tone, and body
proportions - from all angles and reproduce it consistently.

Two images are produced from the same references:

* a straight-on front view, and
* a three-quarter view (the body turned about 30 degrees from the front, head still
  facing the camera).

The front view is generated from the reference photographs. The tilted view is then
derived from that front image (not from the raw references): a reference photo may
itself be a turned or sideways shot, which would anchor the pose and make the model
ignore the requested tilt direction.

Both are polished full-body studio fashion-model photographs of that person, wearing
the exact same outfit as the reference, standing on a plain seamless studio
background. No reference photo appears in either output.

The front image is written to ``--output`` (``assets/avatar/model_generated.png`` by
default) and the tilted image alongside it with a ``_tilted`` suffix
(``assets/avatar/model_generated_tilted.png``). Both are meant to be used the same
way as the existing ``assets/avatar/model.jpg``: as the subject photo for virtual
try-on.

Examples
--------
Generate both views from the default single reference (skips files that exist)::

    uv run python scripts/generate_model.py

Generate from several references of the same person::

    uv run python scripts/generate_model.py \\
        --reference-image photo_front.jpg photo_side.jpg face.jpg \\
        --output assets/avatar/model_generated.png

Regenerate only the tilted view, turning the other way and further::

    uv run python scripts/generate_model.py --views tilted --overwrite \\
        --tilt-direction left --tilt-degrees 35

Force a regeneration even if the outputs already exist::

    uv run python scripts/generate_model.py --overwrite

The OpenRouter API key, endpoint, model, aspect ratio, seed, and timeout all come
from ``closet_muse.settings`` (``.env`` is loaded automatically). The model is
``IMAGE_MODEL_FASHION_MODEL``; ``--model`` overrides it for a single run, and
``--api-key`` overrides the key.
"""

from __future__ import annotations

import argparse
import base64
import sys
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageOps

from closet_muse.settings import settings

DEFAULT_REFERENCE_IMAGES = ["assets/avatar/model_ref.JPG"]
DEFAULT_OUTPUT = "assets/avatar/model_generated.png"
# Suffix appended to the front output path to derive the tilted-view path.
TILTED_SUFFIX = "_tilted"
# Tilted view: which side of the IMAGE the forward shoulder is on, and how far the
# body is rotated from the front (degrees). The image model reliably follows
# image-relative wording ("the shoulder on the left side of the image") but ignores
# anatomical left/right, so the prompt is written in image-relative terms.
DEFAULT_TILT_DIRECTION = "right"
DEFAULT_TILT_DEGREES = 30
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

{view_block}
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

# Sections 2 (FRAMING) and 3 (POSE) of the prompt, one block per view. The rest of
# the prompt is shared, so both views keep the same subject, wardrobe, lighting, and
# output-quality rules.
VIEW_FRONT = """2. FRAMING
* Straight-on front view of the whole person, from the top of the head down to the feet.
* Centered in the frame with a small even margin of empty background around the person.
* One image only: no side-by-side, no before/after, no reference photo in frame, no divider.

3. POSE
* Simple upright, neutral standing posture.
* Arms held relaxed and slightly away from the sides.
* Legs straight with a small natural gap; feet facing forward.
* Static and relaxed; no bending or twisting.
"""

VIEW_TILTED = """2. FRAMING
* A three-quarter view of the whole person, from the top of the head down to the feet.
* The body is turned about {degrees} degrees away from the front. The shoulder on the {direction} side of the image is closer to the camera (forward) and the shoulder on the {opposite} side of the image is further away (back).
* The head stays turned toward the camera and looks straight at it, so the face is fully visible and front-facing.
* Centered in the frame with a small even margin of empty background around the person, at the same scale and framing as a straight-on front view.
* One image only: no side-by-side, no before/after, no reference photo in frame, no divider.

3. POSE
* Simple upright, neutral standing posture with the body turned to a three-quarter angle.
* The shoulder on the {direction} side of the image is forward, closer to the camera.
* Arms held relaxed and slightly away from the sides.
* Legs straight with a small natural gap; both feet remain visible and face roughly forward.
* Static and relaxed; no bending or twisting.
"""

# View name -> prompt block. "front" is the straight-on view, "tilted" the slight
# three-quarter view.
VIEW_BLOCKS = {
    "front": VIEW_FRONT,
    "tilted": VIEW_TILTED,
}

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


def _build_prompt(
    num_references: int,
    view: str = "front",
    tilt_direction: str = DEFAULT_TILT_DIRECTION,
    tilt_degrees: int = DEFAULT_TILT_DEGREES,
) -> str:
    """Build the model prompt for a view, adding multi-reference guidance when needed.

    ``view`` selects the framing/pose block: ``"front"`` (straight-on) or
    ``"tilted"`` (three-quarter turn). For the tilted view, ``tilt_direction`` is the
    side of the image the forward shoulder is on (``"left"`` or ``"right"``) and
    ``tilt_degrees`` is how far the body is rotated from the front.
    """
    if view not in VIEW_BLOCKS:
        raise ValueError(f"view must be one of {sorted(VIEW_BLOCKS)}, got {view!r}")
    if tilt_direction not in ("left", "right"):
        raise ValueError(f"tilt_direction must be 'left' or 'right', got {tilt_direction!r}")
    guidance = MULTI_REFERENCE_GUIDANCE if num_references > 1 else ""
    view_block = VIEW_BLOCKS[view]
    if view == "tilted":
        opposite = "right" if tilt_direction == "left" else "left"
        view_block = view_block.format(
            direction=tilt_direction, opposite=opposite, degrees=tilt_degrees
        )
    return PROMPT_MODEL_TEMPLATE.format(
        reference_guidance=guidance, view_block=view_block
    )


def _tilted_path(output: Path) -> Path:
    """Return the tilted-view path derived from the front output path.

    ``assets/avatar/model_generated.png`` -> ``assets/avatar/model_generated_tilted.png``.
    """
    return output.with_name(f"{output.stem}{TILTED_SUFFIX}{output.suffix}")


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

    response = requests.post(
        settings.openrouter_image_url, json=payload, headers=headers, timeout=timeout
    )
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
            "One or more photos of the same person, used to build the front view. "
            "Multiple photos (different angles or a face close-up) improve identity "
            "consistency. The tilted view is derived from the generated front image."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT),
        help=(
            "Path where the front-view model image is written. The tilted view is "
            "written alongside it with a '_tilted' suffix."
        ),
    )
    parser.add_argument(
        "--views",
        nargs="+",
        choices=["all", "front", "tilted"],
        default=["all"],
        help="Which model views to generate.",
    )
    parser.add_argument(
        "--tilt-direction",
        choices=["left", "right"],
        default=DEFAULT_TILT_DIRECTION,
        help=(
            "For the tilted view: which side of the image the forward shoulder is on "
            "(the body turns so that shoulder is closer to the camera)."
        ),
    )
    parser.add_argument(
        "--tilt-degrees",
        type=int,
        default=DEFAULT_TILT_DEGREES,
        help="For the tilted view: how far the body is rotated from the front, in degrees.",
    )
    parser.add_argument(
        "--model",
        default=settings.image_model_fashion_model,
        help="Image model to use (defaults to IMAGE_MODEL_FASHION_MODEL).",
    )
    parser.add_argument(
        "--aspect-ratio",
        default=settings.image_aspect_ratio,
        help="Output aspect ratio; taller values suit a full-body portrait (e.g. 2:3, 3:4).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=settings.image_seed,
        help="Seed for reproducibility.",
    )
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
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenRouter API key (else OPENROUTER_API_KEY from the environment/.env).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=settings.image_timeout,
        help="Request timeout (seconds).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate even if the output file already exists.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Resolve the requested views to their output paths. The tilted view is derived
    # from the front output path with a '_tilted' suffix.
    outputs = {
        "front": args.output,
        "tilted": _tilted_path(args.output),
    }
    views = ["front", "tilted"] if "all" in args.views else list(args.views)

    # The tilted view is derived from the front image, so the front image must exist
    # before the tilted view can run. If it is missing and was not requested, add it.
    if "tilted" in views and "front" not in views and not outputs["front"].exists():
        views = ["front", *views]

    # Skip any view whose file already exists unless --overwrite was given.
    pending = [view for view in views if args.overwrite or not outputs[view].exists()]
    for view in views:
        if view not in pending:
            print(f"skip  {outputs[view]} (exists; use --overwrite)")
    if not pending:
        return 0

    api_key = args.api_key or settings.openrouter_api_key
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

    print(f"gen   references={len(references)}")
    for reference in references:
        print(f"      {reference}")

    for view in pending:
        output = outputs[view]
        output.parent.mkdir(parents=True, exist_ok=True)
        if view == "front":
            # The front view is built from the reference photographs.
            prompt = _build_prompt(len(references), "front")
            reference_paths = references
        else:
            # The tilted view is derived from the clean front image, not the raw
            # references: a reference photo may itself be a turned or sideways shot,
            # which would anchor the pose and make the model ignore the tilt.
            prompt = _build_prompt(
                1,
                "tilted",
                tilt_direction=args.tilt_direction,
                tilt_degrees=args.tilt_degrees,
            )
            reference_paths = [outputs["front"]]
        print(f"view  {view} -> {output}")
        try:
            image_bytes = _generate(
                api_key=api_key,
                model=args.model,
                prompt=prompt,
                reference_paths=reference_paths,
                aspect_ratio=args.aspect_ratio,
                seed=args.seed,
                timeout=args.timeout,
                max_dimension=args.max_dimension,
                jpeg_quality=args.jpeg_quality,
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure to the user
            print(f"error: {exc}", file=sys.stderr)
            return 1

        output.write_bytes(image_bytes)
        print(f"saved {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
