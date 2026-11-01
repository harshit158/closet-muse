"""Generate the reusable fashion-mannequin images used for virtual try-on.

The pipeline produces four mannequins:

    front   <- the original person photo (``--reference-image``)
    side    <- the generated *front* mannequin (with the ``--side-direction`` view applied)
    top     <- the generated *front* mannequin (upper-body display form)
    bottom  <- the generated *front* mannequin (lower-body display form)

``front`` must be generated (or already exist) before ``side``/``top``/``bottom``
can run, because those three use the front mannequin as their input reference.

Examples
--------
Regenerate everything (skips files that already exist)::

    uv run python scripts/generate_mannequins.py

Force a full regeneration into a custom folder::

    uv run python scripts/generate_mannequins.py --overwrite --output-dir assets/avatar

Regenerate only the side and top views::

    uv run python scripts/generate_mannequins.py --views side top --overwrite

Generate a right-facing side profile instead of the default left::

    uv run python scripts/generate_mannequins.py --views side --side-direction right

The OpenRouter API key is read from the ``OPENROUTER_API_KEY`` environment
variable (``.env`` is loaded automatically if present).
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import sys
from pathlib import Path

import requests

try:  # optional convenience: load a local .env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:  # pragma: no cover - dotenv is a project dependency
    pass

API_URL = "https://openrouter.ai/api/v1/images"
DEFAULT_MODEL = "meta/muse-image"
DEFAULT_REFERENCE_IMAGE = "assets/avatar/model.jpg"
DEFAULT_FRONT_MANNEQUIN = "assets/avatar/mannequin_front.png"
DEFAULT_OUTPUT_DIR = "assets/avatar"
DEFAULT_ASPECT_RATIO = "2:3"
DEFAULT_SEED = 42
DEFAULT_TIMEOUT = 180

# Output filename for each view (kept in sync with the frontend / notebook).
FILENAMES = {
    "front": "mannequin_front.png",
    "side": "mannequin_side.png",
    "top": "mannequin_top.png",
    "bottom": "mannequin_bottom.png",
}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_FRONT = """
Using the uploaded photograph of a real person as the style reference, create a high-quality studio mannequin display form for the FULL BODY, used for virtual clothing try-on and fashion visualization.

OBJECTIVE:
Create a clean studio mannequin shown from the top of the head down to the feet, matching the uploaded photograph so its proportions stay consistent. The result is a display prop used to showcase dresses and complete outfits.

1. SUBJECT
* A clearly artificial, stylized studio mannequin: an inanimate manufactured display object, not a person.
* Smooth, uniform matte beige finish, like painted fiberglass or porcelain.
* Simple, abstract, obviously non-realistic form.
* No realistic human skin, no detailed surface texture, no facial detail.
* Neutral, simplified head shape.
* No hair, jewelry, accessories, or styling.

2. FORM AND PROPORTIONS
* Match the overall shape and dimensions shown in the uploaded photograph.
* Keep the natural shoulder width, torso length, waist width, hip width, and leg length.
* Keep both arms and both legs fully visible.
* Do not reshape, exaggerate, or restyle the form.

3. VIEW AND FRAMING
* Show the mannequin from the top of the head down to the feet.
* Straight-on front view, centered with plain, empty space around the form.

4. POSE
* Simple upright, symmetrical neutral posture.
* Arms held slightly away from the sides.
* Legs straight with a small natural gap; feet facing forward.
* Static and relaxed; no bending or twisting.

5. LIGHTING AND BACKGROUND
* Soft, even studio lighting with minimal shadows.
* Plain, seamless light grey or white background.
* No props or environmental objects.

6. OUTPUT QUALITY
* High-resolution render with a clean silhouette.
* Clearly reads as a professional display mannequin for showcasing garments.
* Suitable as a reusable reference for virtual clothing try-on.

IMPORTANT:
The subject is an artificial display mannequin prop.
"""

PROMPT_SIDE_TEMPLATE = """
Using the uploaded front-view mannequin image as the style reference, create a high-quality studio mannequin display form seen in a TRUE SIDE PROFILE, used for virtual clothing try-on and fashion visualization.

OBJECTIVE:
Render the uploaded front-view mannequin as a strict side profile, matching its shape and appearance so both views stay consistent. The result is a display prop used to showcase dresses and complete outfits.

1. SUBJECT
* A clearly artificial, stylized studio mannequin: an inanimate manufactured display object, not a person.
* Smooth, uniform matte beige finish, like painted fiberglass or porcelain.
* Simple, abstract, obviously non-realistic form.
* No realistic human skin, no detailed surface texture, no facial detail.
* Neutral, simplified head shape.
* No hair, jewelry, accessories, or styling.

2. FORM AND PROPORTIONS
* Keep the same overall shape and dimensions as the uploaded front-view mannequin.
* Match the shoulder depth, torso length, and leg length as seen from the side.
* Keep both arms and both legs fully visible.
* Do not reshape, exaggerate, or restyle the form.

3. VIEW AND FRAMING
* TRUE SIDE PROFILE: the form is rotated 90 degrees so the camera sees the full side, not the front.
* The form faces to the {direction} side of the frame.
* Show the mannequin from the top of the head down to the feet.
* Centered with plain, empty space around the form.

4. POSE
* Simple upright, symmetrical neutral posture with a straight spine.
* Arms held slightly away from the sides.
* Legs straight with a small natural gap; feet facing sideways in profile.
* Static and relaxed; no bending or twisting.

5. LIGHTING AND BACKGROUND
* Soft, even studio lighting with minimal shadows.
* Plain, seamless light grey or white background.
* No props or environmental objects.

6. OUTPUT QUALITY
* High-resolution render with a clean silhouette.
* Clearly reads as a professional display mannequin for showcasing garments.
* Suitable as a reusable reference for virtual clothing try-on.

IMPORTANT:
Keep the same material, color, and style as the uploaded front-view mannequin. The subject is an artificial display mannequin prop. The output must be a strict side profile (90 degrees from the front), not a three-quarter or front-facing view.
"""

PROMPT_TOP = """
Using the uploaded front-view mannequin image as the style reference, create a high-quality studio mannequin display form for the UPPER BODY, used for virtual clothing try-on (tops, blouses, sweaters, jackets, shirts) and fashion visualization.

OBJECTIVE:
Create a clean studio mannequin shown from the head down to the upper hips, matching the uploaded front-view mannequin so its appearance stays consistent. The result is a display prop used to showcase tops, blouses, sweaters, and jackets.

1. SUBJECT
* A clearly artificial, stylized studio mannequin: an inanimate manufactured display object, not a person.
* Smooth, uniform matte beige finish, like painted fiberglass or porcelain.
* Simple, abstract, obviously non-realistic form.
* No realistic human skin, no detailed surface texture, no facial detail.
* Neutral, simplified head shape.
* No hair, jewelry, accessories, or styling.

2. FORM AND PROPORTIONS
* Keep the same overall shape and dimensions as the uploaded front-view mannequin.
* Match the shoulder width, torso length, waist width, and arm length.
* Keep both arms visible.
* Do not reshape, exaggerate, or restyle the form.

3. VIEW AND FRAMING
* Show the mannequin from the top of the head down to the upper hips.
* Straight-on front view.
* Centered with plain, empty space around the form.

4. POSE
* Simple upright, symmetrical neutral posture.
* Arms held slightly away from the sides.
* Static and relaxed; no bending or twisting.

5. LIGHTING AND BACKGROUND
* Soft, even studio lighting with minimal shadows.
* Plain, seamless light grey or white background.
* No props or environmental objects.

6. OUTPUT QUALITY
* High-resolution render with a clean silhouette.
* Clearly reads as a professional display mannequin for showcasing garments.
* Suitable as a reusable reference for virtual clothing try-on.

IMPORTANT:
Keep the same material, color, and style as the uploaded front-view mannequin. The subject is an artificial display mannequin prop.
"""

PROMPT_BOTTOM = """
Using the uploaded front-view mannequin image as the style reference, create a high-quality studio mannequin display form for the LOWER BODY, used for virtual clothing try-on (pants, trousers, skirts, shorts) and fashion visualization.

OBJECTIVE:
Create a clean studio mannequin shown from the waist down to the feet, matching the uploaded front-view mannequin so its appearance stays consistent. The result is a display prop used to showcase pants, trousers, jeans, skirts, and shorts.

1. SUBJECT
* A clearly artificial, stylized studio mannequin: an inanimate manufactured display object, not a person.
* Smooth, uniform matte beige finish, like painted fiberglass or porcelain.
* Simple, abstract, obviously non-realistic form.
* No realistic human skin, no detailed surface texture.
* No jewelry, accessories, or styling.

2. FORM AND PROPORTIONS
* Keep the same overall shape and dimensions as the uploaded front-view mannequin.
* Match the waist width, hip width, and leg length.
* Keep both legs fully visible.
* Do not reshape, exaggerate, or restyle the form.

3. VIEW AND FRAMING
* Show the mannequin from the waist down to the feet.
* Straight-on front view.
* Centered with plain, empty space around the form.

4. POSE
* Simple upright, symmetrical neutral posture.
* Legs straight with a small natural gap.
* Feet facing forward.
* Static and relaxed; no bending or twisting.

5. LIGHTING AND BACKGROUND
* Soft, even studio lighting with minimal shadows.
* Plain, seamless light grey or white background.
* No props or environmental objects.

6. OUTPUT QUALITY
* High-resolution render with a clean silhouette.
* Clearly reads as a professional display mannequin for showcasing garments.
* Suitable as a reusable reference for virtual clothing try-on.

IMPORTANT:
Keep the same material, color, and style as the uploaded front-view mannequin. The subject is an artificial display mannequin prop.
"""


def _to_data_url(path: Path) -> str:
    """Return a ``data:`` URL for the image at ``path``."""
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _generate(
    *,
    api_key: str,
    model: str,
    prompt: str,
    reference_path: Path,
    aspect_ratio: str,
    seed: int,
    timeout: int,
) -> bytes:
    """Call the OpenRouter image API and return the generated PNG bytes."""
    if not reference_path.is_file():
        raise FileNotFoundError(f"Reference image not found: {reference_path}")

    payload = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "input_references": [
            {"type": "image_url", "image_url": {"url": _to_data_url(reference_path)}}
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


def _build_prompts(side_direction: str) -> dict[str, str]:
    return {
        "front": PROMPT_FRONT,
        "side": PROMPT_SIDE_TEMPLATE.format(direction=side_direction),
        "top": PROMPT_TOP,
        "bottom": PROMPT_BOTTOM,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the reusable fashion-mannequin images.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--views",
        nargs="+",
        choices=["all", "front", "side", "top", "bottom"],
        default=["all"],
        help="Which mannequins to generate.",
    )
    parser.add_argument(
        "--reference-image",
        type=Path,
        default=Path(DEFAULT_REFERENCE_IMAGE),
        help="Person photo used as the reference for the front mannequin.",
    )
    parser.add_argument(
        "--mannequin-image",
        type=Path,
        default=Path(DEFAULT_FRONT_MANNEQUIN),
        help=(
            "Front mannequin used as the reference for the side/top/bottom views. "
            "Defaults to <output-dir>/mannequin_front.png."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help="Directory where the generated mannequins are written.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Image model to use.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Seed for reproducibility.")
    parser.add_argument(
        "--side-direction",
        choices=["left", "right"],
        default="left",
        help="Direction the side-profile mannequin faces.",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout (seconds).")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate views even if their output file already exists.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    views = list(FILENAMES) if "all" in args.views else args.views
    # Keep a deterministic, dependency-safe order: front before the derived views.
    views = [v for v in ["front", "side", "top", "bottom"] if v in views]

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print(
            "error: no API key. Set the OPENROUTER_API_KEY environment variable.",
            file=sys.stderr,
        )
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    prompts = _build_prompts(args.side_direction)
    outputs = {view: args.output_dir / FILENAMES[view] for view in FILENAMES}

    # Reference used by the derived views (side/top/bottom).
    front_reference = args.mannequin_image or Path(DEFAULT_FRONT_MANNEQUIN)

    for view in views:
        output_path = outputs[view]

        if output_path.exists() and not args.overwrite:
            print(f"skip  {view:<6} {output_path} (exists; use --overwrite)")
            continue

        if view == "front":
            reference = args.mannequin_image or Path(DEFAULT_REFERENCE_IMAGE)
            prompt = prompts["front"]
        else:
            if not front_reference.is_file():
                print(
                    f"error: front mannequin not found at {front_reference}. "
                    f"Generate the front view first (--views front).",
                    file=sys.stderr,
                )
                return 1
            reference = front_reference
            prompt = prompts[view]

        print(f"gen   {view:<6} reference={reference}")
        try:
            image_bytes = _generate(
                api_key=api_key,
                model=args.model,
                prompt=prompt,
                reference_path=reference,
                aspect_ratio=DEFAULT_ASPECT_RATIO,
                seed=args.seed,
                timeout=args.timeout,
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure to the user
            print(f"error {view}: {exc}", file=sys.stderr)
            return 1

        output_path.write_bytes(image_bytes)
        print(f"saved {view:<6} {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
