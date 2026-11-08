"""Generate the reusable fashion-mannequin images used for virtual try-on.

The pipeline produces ten mannequins: five display forms, each in a straight-on
front view and a three-quarter tilted view.

    form     front reference              tilted reference
    -------  ---------------------------  --------------------------
    full     the original person photo    mannequin_full.png
    face     mannequin_full.png           mannequin_face.png
    top      mannequin_full.png           mannequin_top.png
    bottom   mannequin_full.png           mannequin_bottom.png
    feet     mannequin_full.png           mannequin_feet.png

``full`` must be generated (or already exist) before ``face``/``top``/``bottom``/
``feet`` can run, because those four use the full-body mannequin as their input
reference. Each tilted view is derived from its own form's *front* image rather
than from the raw reference, so the requested turn is not anchored by the pose of
the reference photograph.

Examples
--------
Regenerate everything (skips files that already exist)::

    uv run python scripts/generate_mannequins.py

Force a full regeneration into a custom folder::

    uv run python scripts/generate_mannequins.py --overwrite --output-dir assets/avatar

Regenerate only the face and top forms, both views::

    uv run python scripts/generate_mannequins.py --forms face top --overwrite

Regenerate only the tilted views of every form::

    uv run python scripts/generate_mannequins.py --views tilted --overwrite

Regenerate only the footwear form::

    uv run python scripts/generate_mannequins.py --forms feet --overwrite

Turn the other way, and further, for the tilted views::

    uv run python scripts/generate_mannequins.py --views tilted --overwrite \\
        --tilt-direction left --tilt-degrees 35

The OpenRouter API key is read from the ``OPENROUTER_API_KEY`` environment
variable (``.env`` is loaded automatically if present).
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import sys
from io import BytesIO
from pathlib import Path

import requests

try:  # optional convenience: load a local .env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:  # pragma: no cover - dotenv is a project dependency
    pass

API_URL = "https://openrouter.ai/api/v1/images"
DEFAULT_MODEL = "openai/gpt-image-2.5-sunburst" # "meta/muse-image"
DEFAULT_REFERENCE_IMAGE = "assets/avatar/model_generated.png"
DEFAULT_FULL_MANNEQUIN = "assets/avatar/mannequin_full.png"
DEFAULT_OUTPUT_DIR = "assets/avatar"
DEFAULT_ASPECT_RATIO = "2:3"
DEFAULT_TIMEOUT = 180
# Tilted view: which side of the IMAGE the forward shoulder is on, and how far the
# body is rotated from the front (degrees). The image model reliably follows
# image-relative wording ("the shoulder on the left side of the image") but ignores
# anatomical left/right, so the prompt is written in image-relative terms.
DEFAULT_TILT_DIRECTION = "right"
DEFAULT_TILT_DEGREES = 60

# The five display forms, in generation order (``full`` first: the other four use
# it as their reference).
FORMS = ("full", "face", "top", "bottom", "feet")
# The two views generated for every form.
VIEWS = ("front", "tilted")


def mannequin_filename(form: str, view: str) -> str:
    """Return the output filename for a form and view.

    ``mannequin_full.png`` for the front view, ``mannequin_full_tilted.png`` for
    the three-quarter view.
    """
    suffix = "" if view == "front" else "_tilted"
    return f"mannequin_{form}{suffix}.png"


# Output filename for every (form, view) pair (kept in sync with the frontend).
FILENAMES = {
    (form, view): mannequin_filename(form, view) for form in FORMS for view in VIEWS
}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
#
# Every form and every view shares ONE prompt shape, because the image provider's
# content filter is sensitive to how the request is structured:
#
#   OBJECTIVE, 1. SUBJECT, 2. FORM AND PROPORTIONS, 3. VIEW AND FRAMING,
#   4. POSE, 5. LIGHTING AND BACKGROUND, 6. OUTPUT QUALITY, IMPORTANT:
#
# Only the placeholders change per form/view. Keep the section shape and the
# "artificial display form" wording intact - see /memories/repo/image-prompts.md
# for the filter triggers to avoid.

PROMPT_TEMPLATE = """
Using the uploaded {reference_description} as the style reference, create a high-quality studio mannequin display form for the {form_title}, used for virtual clothing try-on and fashion visualization.

OBJECTIVE:
{objective}

1. SUBJECT
* A clearly artificial, stylized studio mannequin: an inanimate manufactured display object, not a person.
* Smooth, uniform matte whitish finish (soft off-white, very pale warm white), like painted fiberglass or porcelain.
* Simple, abstract, obviously non-realistic form.
* No realistic human skin, no detailed surface texture, no facial detail.
* Neutral, simplified head shape.
* No hair, jewelry, accessories, or styling.
{subject_extra}
2. FORM AND PROPORTIONS
* Match the overall shape and dimensions shown in the uploaded {reference_description}.
* {proportions}
* Do not reshape, exaggerate, or restyle the form.

3. VIEW AND FRAMING
{view_block}

4. POSE
{pose_block}

5. LIGHTING AND BACKGROUND
* Soft, even studio lighting with minimal shadows.
* Plain, seamless light grey or white background.
* No props or environmental objects.
{lighting_extra}
6. OUTPUT QUALITY
* High-resolution render with a clean silhouette.
* Clearly reads as a professional display mannequin for showcasing garments.
* Suitable as a reusable reference for virtual clothing try-on.

IMPORTANT:
{important}
"""

# Per-form text: the title, objective, any extra SUBJECT bullets, the proportions
# rule, and the trailing IMPORTANT block. ``subject_extra`` must end with a newline
# when non-empty so the blank line before section 2 is preserved.
FORM_BLOCKS = {
    "full": {
        "form_title": "FULL BODY",
        "objective": (
            "Create a clean studio mannequin shown from the top of the head down to the "
            "feet, matching the uploaded photograph so its proportions stay consistent. "
            "The result is a display prop used to showcase dresses and complete outfits."
        ),
        "subject_extra": "",
        "proportions": (
            "Keep the natural shoulder width, torso length, waist width, hip width, and "
            "leg length.\n* Keep both arms and both legs fully visible."
        ),
        "lighting_extra": (
            "* A soft, subtle contact shadow directly beneath the feet shows they are "
            "resting flat on the floor.\n"
        ),
        "important": (
            "The subject is an artificial display mannequin prop.\n"
            "Both feet rest flat on the floor: the heels are down and the whole sole of "
            "each foot is in full contact with the ground, with no raised heels, no "
            "tiptoe, and no floating or hovering feet."
        ),
    },
    "face": {
        "form_title": "HEAD, NECK AND SHOULDERS",
        "objective": (
            "Create a clean studio mannequin shown from the top of the head down to the "
            "shoulders, matching the uploaded front-view mannequin so its appearance stays "
            "consistent. The result is a display prop used to showcase hats, sunglasses, "
            "earrings, necklaces, and scarves."
        ),
        "subject_extra": (
            "* The head, neck, and shoulders show only the mannequin's own smooth neutral "
            "matte surface, the same finish as the rest of the form.\n"
            "* Do not copy, transfer, or reproduce any clothing or accessory seen in the "
            "uploaded reference; the outfit in the uploaded picture is not part of this "
            "output.\n"
        ),
        "proportions": (
            "Match the head size, neck length, and shoulder width of the uploaded "
            "front-view mannequin.\n* Keep both shoulders fully visible."
        ),
        "lighting_extra": "",
        "important": (
            "Keep the same material, color, and style as the uploaded front-view mannequin. "
            "The subject is an artificial display mannequin prop.\n"
            "Show only the mannequin's own neutral display surface, and do not reproduce any "
            "clothing or accessory from the uploaded reference. The frame ends at the "
            "shoulders and must not be extended downward."
        ),
    },
    "top": {
        "form_title": "UPPER BODY",
        "objective": (
            "Create a clean studio mannequin shown from the head down to the upper hips, "
            "matching the uploaded front-view mannequin so its appearance stays consistent. "
            "The result is a display prop used to showcase tops, blouses, sweaters, and "
            "jackets."
        ),
        "subject_extra": (
            "* Upper body shows only the mannequin's own smooth neutral matte surface, the "
            "same finish as the head, neck, and arms.\n"
            "* To keep the form looking complete, the lower body wears a plain, simple "
            "neutral legging (light grey, beige, or off-white), smooth and unpatterned with "
            "no logos, prints, or detail.\n"
            "* Do not copy, transfer, or reproduce any clothing seen in the uploaded "
            "reference; the outfit in the uploaded picture is not part of this output.\n"
        ),
        "proportions": (
            "Match the shoulder width, torso length, waist width, and arm length of the "
            "uploaded front-view mannequin.\n* Keep both arms visible."
        ),
        "lighting_extra": "",
        "important": (
            "Keep the same material, color, and style as the uploaded front-view mannequin. "
            "The subject is an artificial display mannequin prop.\n"
            "Show only the mannequin's own neutral display surface and the plain neutral "
            "legging, and do not reproduce any clothing from the uploaded reference. The "
            "frame ends at the upper hips and must not be extended downward."
        ),
    },
    "bottom": {
        "form_title": "LOWER BODY",
        "objective": (
            "Create a clean studio mannequin shown from the waist down to the feet, matching "
            "the uploaded front-view mannequin so its appearance stays consistent. The result "
            "is a display prop used to showcase pants, trousers, jeans, skirts, and shorts."
        ),
        "subject_extra": "",
        "proportions": (
            "Match the waist width, hip width, and leg length of the uploaded front-view "
            "mannequin.\n* Keep both legs fully visible."
        ),
        "lighting_extra": (
            "* A soft, subtle contact shadow directly beneath the feet shows they are "
            "resting flat on the floor.\n"
        ),
        "important": (
            "Keep the same material, color, and style as the uploaded front-view mannequin. "
            "The subject is an artificial display mannequin prop.\n"
            "Both feet rest flat on the floor: the heels are down and the whole sole of "
            "each foot is in full contact with the ground, with no raised heels, no "
            "tiptoe, and no floating or hovering feet."
        ),
    },
    "feet": {
        "form_title": "LOWER LEGS AND FEET",
        "objective": (
            "Create a clean studio mannequin display form cropped tightly from the knees down "
            "to the feet, matching the uploaded front-view mannequin so its appearance stays "
            "consistent. The top edge of the frame is at the kneecaps, so zero thigh is "
            "visible. The tight crop makes the lower legs and feet fill the frame and the "
            "footwear read large. The result is a display prop used to showcase footwear."
        ),
        "subject_extra": "",
        "proportions": (
            "Match the lower-leg length and foot size of the uploaded front-view mannequin.\n"
            "* Keep both lower legs and both feet fully visible."
        ),
        "lighting_extra": (
            "* A soft, subtle contact shadow directly beneath the feet shows they are "
            "resting flat on the floor.\n"
        ),
        "important": (
            "Keep the same material, color, and style as the uploaded front-view mannequin. "
            "The subject is an artificial display mannequin prop.\n"
            "Both feet rest flat on the floor: the heels are down and the whole sole of "
            "each foot is in full contact with the ground, with no raised heels, no "
            "tiptoe, and no floating or hovering feet.\n"
            "The top edge of the image is at the kneecaps: no thighs, upper legs, hips, or "
            "upper body may be visible anywhere in the frame. The frame contains only the "
            "knees, lower legs, and feet."
        ),
    },
}

# Section 3 crop text per form. The crop is IDENTICAL for the front and tilted
# views, so it is written once here and reused by both.
CROP_BY_FORM = {
    "full": "* Show the mannequin from the top of the head down to the feet.",
    "face": (
        "* Show the mannequin from the top of the head down to the shoulders only; this is "
        "much shorter than the uploaded full-length reference.\n"
        "* The bottom edge of the frame is at the shoulders. Do not extend the frame "
        "downward and do not zoom out: nothing below the shoulders may appear (no chest, "
        "torso, waist, hips, legs, or feet).\n"
        "* The head is centered in the frame and fills most of it, so the head, neck, and "
        "shoulders read large."
    ),
    "top": (
        "* Show the mannequin from the top of the head down to the upper hips only; this is "
        "much shorter than the uploaded full-length reference.\n"
        "* The bottom edge of the frame is at the upper hips. Do not extend the frame "
        "downward and do not zoom out: nothing below the upper hips may appear (no lower "
        "torso, legs, knees, lower legs, or feet).\n"
        "* Only the top edge of the plain neutral base bottom below the waist falls inside "
        "the frame.\n"
        "* The plain neutral legging below the waist is visible only from the waist down to "
        "the crop line at the upper hips; nothing of the legging below the upper hips may be "
        "shown."
    ),
    "bottom": "* Show the mannequin from the waist down to the feet.",
    "feet": (
        "* The image is a tight vertical crop of the legs, from the knees down to the feet.\n"
        "* The TOP EDGE of the image cuts across the kneecaps. Nothing above the kneecaps is "
        "visible: no thighs, no upper legs, no hips, no upper body. If any part of a thigh "
        "would appear, crop it out.\n"
        "* The BOTTOM EDGE of the image is just below the feet, with a small margin of "
        "background under them.\n"
        "* Frame tightly around the lower legs and feet so they fill the frame, leaving only "
        "a narrow margin of plain background on each side.\n"
        "* The footwear is large and clearly readable."
    ),
}

# Section 3 for the straight-on view: the form's crop plus the camera position.
VIEW_FRONT_BLOCK = (
    "{crop}\n"
    "* Straight-on front view.\n"
    "* Centered with plain, empty space around the form."
)

# Section 3 for the three-quarter view. The turn is described in IMAGE-RELATIVE
# terms ("the shoulder on the left side of the image") because the image model
# ignores anatomical left/right - see /memories/repo/scripts.md.
TILT_BLOCK_UPPER = (
    "* A three-quarter view: the form is turned about {degrees} degrees away from the "
    "front. The shoulder on the {direction} side of the image is closer to the camera "
    "(forward) and the shoulder on the {opposite} side of the image is further away "
    "(back).\n"
    "* The head turns together with the body, in the same direction and by the same "
    "amount: the whole form rotates as one piece.\n"
    "* The face is therefore seen at a three-quarter angle, not straight-on. The head "
    "does not stay front-facing and does not turn back toward the camera.\n"
    "* Centered with plain, empty space around the form, at the same scale and framing as "
    "the straight-on front view."
)
TILT_BLOCK_LOWER = (
    "* A three-quarter view: the form is turned about {degrees} degrees away from the "
    "front. The leg on the {direction} side of the image is closer to the camera (forward) "
    "and the leg on the {opposite} side of the image is further away (back).\n"
    "* Centered with plain, empty space around the form, at the same scale and framing as "
    "the straight-on front view."
)

# Which tilt wording a form uses: upper-body forms turn at the shoulders, lower-body
# forms turn at the legs.
TILT_BLOCK_BY_FORM = {
    "full": TILT_BLOCK_UPPER,
    "face": TILT_BLOCK_UPPER,
    "top": TILT_BLOCK_UPPER,
    "bottom": TILT_BLOCK_LOWER,
    "feet": TILT_BLOCK_LOWER,
}

# Section 4 pose text per form, limited to the body parts that are actually in frame.
POSE_BY_FORM = {
    "full": (
        "* Simple upright, symmetrical neutral posture.\n"
        "* Arms held slightly away from the sides.\n"
        "* Legs straight with a small natural gap; feet facing forward.\n"
        "* Both feet stand flat on the floor: the whole sole of each foot, including the "
        "heel, is in full contact with the ground. No raised heels, no tiptoe, no floating "
        "or hovering feet.\n"
        "* Static and relaxed; no bending or twisting."
    ),
    "face": (
        "* Simple upright, neutral posture with the head upright and level.\n"
        "* Shoulders level and relaxed.\n"
        "* Static and relaxed; no bending or twisting."
    ),
    "top": (
        "* Simple upright, symmetrical neutral posture.\n"
        "* Arms held slightly away from the sides.\n"
        "* Static and relaxed; no bending or twisting."
    ),
    "bottom": (
        "* Simple upright, symmetrical neutral posture.\n"
        "* Legs straight with a small natural gap.\n"
        "* Feet facing forward.\n"
        "* Both feet stand flat on the floor: the whole sole of each foot, including the "
        "heel, is in full contact with the ground. No raised heels, no tiptoe, no floating "
        "or hovering feet.\n"
        "* Static and relaxed; no bending or twisting."
    ),
    "feet": (
        "* Simple upright, symmetrical neutral posture.\n"
        "* Lower legs straight with a small natural gap.\n"
        "* Feet facing forward, standing flat.\n"
        "* Both feet stand flat on the floor: the whole sole of each foot, including the "
        "heel, is in full contact with the ground. No raised heels, no tiptoe, no floating "
        "or hovering feet.\n"
        "* Static and relaxed; no bending or twisting."
    ),
}

# Appended to the pose block for the front view, per form. Only the ``face`` form
# needs it: its pose no longer names a head direction (the tilted view turns the
# head with the body), so the front view states it explicitly.
POSE_FRONT_EXTRA_BY_FORM = {
    "face": "* The head faces the camera directly, so the face is fully visible.\n",
}

# Appended to the pose block for the tilted view.
POSE_TILT_EXTRA = (
    "* The body is turned to a three-quarter angle; the posture itself stays neutral and "
    "upright.\n"
    "* The head turns with the body, so the face is seen at the same three-quarter angle "
    "as the shoulders."
)

def build_prompt(
    form: str,
    view: str = "front",
    *,
    tilt_direction: str = DEFAULT_TILT_DIRECTION,
    tilt_degrees: int = DEFAULT_TILT_DEGREES,
) -> str:
    """Build the image prompt for one mannequin form and view.

    ``form`` is one of ``FORMS``; ``view`` is ``front`` or ``tilted``. The
    tilted view is described in image-relative terms (which side of the *image*
    the forward shoulder is on) because the image model ignores anatomical
    left/right wording.
    """
    if form not in FORM_BLOCKS:
        raise ValueError(f"form must be one of {list(FORMS)}, got {form!r}")
    if view not in VIEWS:
        raise ValueError(f"view must be one of {list(VIEWS)}, got {view!r}")

    block = FORM_BLOCKS[form]
    crop = CROP_BY_FORM[form]

    if view == "front":
        view_block = VIEW_FRONT_BLOCK.format(crop=crop)
        pose_block = POSE_BY_FORM[form] + POSE_FRONT_EXTRA_BY_FORM.get(form, "")
    else:
        opposite = "left" if tilt_direction == "right" else "right"
        view_block = (
            crop
            + "\n"
            + TILT_BLOCK_BY_FORM[form].format(
                degrees=tilt_degrees,
                direction=tilt_direction,
                opposite=opposite,
            )
        )
        pose_block = f"{POSE_BY_FORM[form]}\n{POSE_TILT_EXTRA}"

    # The full-body form is generated from the person's photograph; every other
    # form is derived from the generated full-body mannequin.
    reference_description = (
        "photograph of a real person"
        if form == "full"
        else "front-view mannequin image"
    )

    return PROMPT_TEMPLATE.format(
        reference_description=reference_description,
        form_title=block["form_title"],
        objective=block["objective"],
        subject_extra=block["subject_extra"],
        proportions=block["proportions"],
        lighting_extra=block["lighting_extra"],
        view_block=view_block,
        pose_block=pose_block,
        important=block["important"],
    )


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
        "output_format": "png",
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
        description="Generate the reusable fashion-mannequin images.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--forms",
        nargs="+",
        choices=["all", *FORMS],
        default=["all"],
        help="Which mannequin forms to generate.",
    )
    parser.add_argument(
        "--views",
        nargs="+",
        choices=["all", *VIEWS],
        default=["all"],
        help="Which view of each form to generate.",
    )
    parser.add_argument(
        "--reference-image",
        type=Path,
        default=Path(DEFAULT_REFERENCE_IMAGE),
        help="Person photo used as the reference for the full-body mannequin.",
    )
    parser.add_argument(
        "--full-mannequin",
        type=Path,
        default=Path(DEFAULT_FULL_MANNEQUIN),
        help=(
            "Full-body mannequin used as the reference for the face/top/bottom/feet "
            "forms. Defaults to <output-dir>/mannequin_full.png."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help="Directory where the generated mannequins are written.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Image model to use.")
    parser.add_argument(
        "--tilt-direction",
        choices=["left", "right"],
        default=DEFAULT_TILT_DIRECTION,
        help=(
            "Which side of the IMAGE the forward shoulder is on in the tilted view. "
            "The image model ignores anatomical left/right, so this is image-relative."
        ),
    )
    parser.add_argument(
        "--tilt-degrees",
        type=int,
        default=DEFAULT_TILT_DEGREES,
        help="How far the body is turned from the front in the tilted view.",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout (seconds).")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate images even if their output file already exists.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    forms = list(FORMS) if "all" in args.forms else args.forms
    # Keep a deterministic, dependency-safe order: full before the derived forms.
    forms = [form for form in FORMS if form in forms]
    views = list(VIEWS) if "all" in args.views else args.views
    views = [view for view in VIEWS if view in views]

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print(
            "error: no API key. Set the OPENROUTER_API_KEY environment variable.",
            file=sys.stderr,
        )
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        (form, view): args.output_dir / FILENAMES[(form, view)]
        for form in FORMS
        for view in VIEWS
    }

    # Reference used by the derived forms (face/top/bottom/feet).
    full_reference = args.full_mannequin or Path(DEFAULT_FULL_MANNEQUIN)

    # Front views are generated before tilted views so each tilted view can use
    # its own form's front image as the reference.
    for view in views:
        for form in forms:
            output_path = outputs[(form, view)]

            if output_path.exists() and not args.overwrite:
                print(f"skip  {form:<6} {view:<6} {output_path} (exists; use --overwrite)")
                continue

            if form == "full" and view == "front":
                reference = args.reference_image
            elif view == "front":
                if not full_reference.is_file():
                    print(
                        f"error: full-body mannequin not found at {full_reference}. "
                        f"Generate it first (--forms full --views front).",
                        file=sys.stderr,
                    )
                    return 1
                reference = full_reference
            else:
                # Tilted views are derived from their own form's front image, not
                # from the raw reference: a turned reference photo would anchor the
                # pose and make the model ignore the requested tilt direction.
                reference = outputs[(form, "front")]
                if not reference.is_file():
                    print(
                        f"error: front image for the {form} form not found at "
                        f"{reference}. Generate it first (--forms {form} --views front).",
                        file=sys.stderr,
                    )
                    return 1

            prompt = build_prompt(
                form,
                view,
                tilt_direction=args.tilt_direction,
                tilt_degrees=args.tilt_degrees,
            )

            print(f"gen   {form:<6} {view:<6} reference={reference}")
            try:
                image_bytes = _generate(
                    api_key=api_key,
                    model=args.model,
                    prompt=prompt,
                    reference_path=reference,
                    aspect_ratio=DEFAULT_ASPECT_RATIO,
                    timeout=args.timeout,
                )
            except Exception as exc:  # noqa: BLE001 - surface any failure to the user
                print(f"error {form} {view}: {exc}", file=sys.stderr)
                return 1

            output_path.write_bytes(image_bytes)
            print(f"saved {form:<6} {view:<6} {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
