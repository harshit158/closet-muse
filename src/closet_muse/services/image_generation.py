"""Image generation via the OpenRouter image API (``meta/muse-image``).

Two flows use the same API:

* the onboarding "polish" step dresses a reusable studio mannequin in the garment
  worn by the person in the uploaded photo; and
* the outfit generator dresses a model in the selected wardrobe items (virtual try-on).
"""

import base64
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from closet_muse.domain.schemas import ClothingWithImage
from closet_muse.settings import settings

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/images"
OPENROUTER_TIMEOUT = 180

# ---------------------------------------------------------------------------
# Dressed-mannequin prompt (ported from notebooks/open_ai_image_model.ipynb)
# ---------------------------------------------------------------------------

prompt_mannequin_dressed_template = """
Using the uploaded photograph of a real person and the uploaded {view_reference} as references, dress the mannequin in the {garment_type} worn by the person in the photograph, reproducing the exact fit of that garment.

OBJECTIVE:
Transfer the {garment_type} from the person onto the mannequin so the mannequin alone communicates how the garment fits. 
The mannequin must wear the garment with the same fit, drape, and proportions it has on the person, so the fit can be judged by looking at the mannequin instead of the person.

1. GARMENT IDENTIFICATION
* Identify the {garment_type} worn by the person in the photograph.
* Reproduce its exact design: color, fabric, pattern, texture, seams, stitching, hardware, and any logos or prints.
* Do not substitute, restyle, recolor, or redesign the garment.
* Do not add garments that are not part of the {garment_type} (no extra layers, belts, or accessories).

2. FIT AND DRAPE (PRIMARY FOCUS)
* Reproduce the fit exactly as it appears on the person: tight, fitted, regular, relaxed, or oversized.
* Match where the garment is snug and where it is loose.
* Match the tension and pull lines, the natural wrinkles and folds, and how the fabric hangs.
* Match the garment's length: hem position, sleeve length, rise, and inseam.
* Match how the garment sits on the shoulders, chest, waist, hips, and legs.
* Match the silhouette the garment creates on the body.
* Do not tighten, loosen, shorten, lengthen, or idealize the fit in any way.

3. MANNEQUIN FORM AND CROP (MUST MATCH THE REFERENCE)
* The uploaded {view_reference} defines the mannequin's form, view, and crop. Reproduce them exactly.
* Keep the mannequin's body proportions, pose, material, and color identical to the uploaded {view_reference}.
* The mannequin remains an artificial display form: no realistic human skin, no facial detail, no hair.
* The garment must conform to the mannequin's body exactly as it conforms to the person's body, so the same fit is preserved.
* Do not change the mannequin's type: a partial mannequin must stay partial and a full-body mannequin must stay full-body.
* Do not add body parts that are outside the uploaded mannequin image's crop and do not remove any that are inside it.
{complementary_bottom}
4. VIEW AND FRAMING
* {view}
* {framing}
* Centered, with plain empty space around the form.

5. LIGHTING AND BACKGROUND
* Soft, even studio lighting with minimal shadows.
* Plain, seamless light grey or white background.
* No props or environmental objects.

6. OUTPUT QUALITY
* High-resolution render with a clean silhouette.
* The garment's fit is immediately readable from the mannequin alone.
* Suitable as a reusable reference for virtual clothing try-on.

IMPORTANT:
The fit of the {garment_type} on the mannequin must match the fit on the person exactly. The mannequin is an artificial display prop wearing the person's garment.
The output must keep the exact same mannequin form, view, and crop as the uploaded {view_reference}.
{complementary_bottom_note}
"""

# Framing text per mannequin form, so the output crop matches the reference image.
FRAMING_BY_FORM = {
    "full_front": "Show the complete mannequin from head to feet, exactly as framed in the uploaded mannequin image.",
    "full_side": "Show the complete mannequin from head to feet, exactly as framed in the uploaded mannequin image.",
    "top": (
        "Show only the upper body, from the head down to the upper hips, exactly as cropped in the "
        "uploaded mannequin image. Do not extend the crop, and do not add legs or feet."
    ),
    "bottom": (
        "Show only the lower body, from the waist down to the feet, exactly as cropped in the "
        "uploaded mannequin image. Do not extend the crop, and do not add a head or upper body."
    ),
    "feet": (
        "Show only the knees, lower legs, and feet of the display form: the top edge of the "
        "frame is at the kneecaps so no thigh is visible. Match the crop of the uploaded "
        "mannequin image. Do not extend the crop upward to include the thighs, hips, or upper "
        "body, and do not add a head, torso, or arms."
    ),
}

# Camera view per mannequin form, so the output matches the reference image's orientation.
VIEW_BY_FORM = {
    "full_front": "Straight-on front view, matching the uploaded mannequin image.",
    "full_side": (
        "Strict side profile view (90 degrees from the front), matching the uploaded mannequin "
        "image. The body faces to one side and the face direction is perpendicular to the camera. "
        "Do not render a front or three-quarter view."
    ),
    "top": "Straight-on front view, matching the uploaded mannequin image.",
    "bottom": "Straight-on front view, matching the uploaded mannequin image.",
    "feet": "Straight-on front view, matching the uploaded mannequin image.",
}

# How the reference mannequin image is described in the prompt, per form.
VIEW_REFERENCE_BY_FORM = {
    "full_front": "front-view mannequin image",
    "full_side": "side-view mannequin image",
    "top": "front-view mannequin image",
    "bottom": "front-view mannequin image",
    "feet": "front-view mannequin image",
}

# Reference mannequin image filename per form (under ``settings.mannequin_dir``).
MANNEQUIN_FILE_BY_FORM = {
    "full_front": "mannequin_front.png",
    "full_side": "mannequin_side.png",
    "top": "mannequin_top.png",
    "bottom": "mannequin_bottom.png",
    "feet": "mannequin_feet.png",
}

# When the focus garment is a top on a CROPPED (upper-body) mannequin, the mannequin also
# wears a plain, neutral bottom so it does not look unfinished - but ONLY within the
# existing crop. The frame must NOT be extended downward to reveal more of the bottom.
COMPLEMENTARY_BOTTOM_FOR_TOP = """* The mannequin must not be left bare below the waist: dress it in a plain, neutral-colored bottom (light grey, beige, or off-white trousers).
* Show the bottom ONLY within the existing crop. The frame must end exactly where the uploaded mannequin image ends - do NOT extend the crop downward to reveal more of the bottom, legs, thighs, knees, or feet.
* If the uploaded mannequin image is cropped at the upper hips, the output must also be cropped at the upper hips: the bottom is only visible down to that crop line, and nothing below it may be shown.
* Keep the bottom simple and unpatterned, with no logos, prints, or embellishments.
* The bottom must be visually recessive and must not compete with or draw attention from the {garment_type}.
* Do not copy the person's bottom garment; this is a neutral filler only.
"""

COMPLEMENTARY_BOTTOM_NOTE_FOR_TOP = """The neutral bottom is only a filler to keep the mannequin looking complete; it must not distract from the {garment_type}.
The bottom must stay within the existing crop: the frame must end exactly where the uploaded mannequin image ends, and must not be extended downward to reveal more of the bottom.
"""

# When the focus item is footwear on the CROPPED (lower-legs and feet) mannequin, the display
# form must actually be shown WEARING the shoes, so the product is the visible subject.
FOOTWEAR_ON_FORM = """* The display form must be shown wearing the {garment_type} on its feet: the shoes are the subject and must be fully visible and clearly readable.
* Present the pair as a matching set: keep the left and right shoe identical in design, color, and finish.
* Reproduce the exact design: color, material, texture, pattern, sole shape, heel height, closures, stitching, and any logos or prints.
* Do not substitute, restyle, recolor, or redesign the shoes.
* Do not add any other item to the form (no clothing, hosiery, socks, or accessories) beyond what the uploaded photograph shows.
* Do not show the form without the {garment_type} on its feet.
"""

FOOTWEAR_ON_FORM_NOTE = """The {garment_type} must be worn on the display form's feet and must be the clearly visible subject.
The form must stay within the existing crop: the frame must end exactly where the uploaded mannequin image ends, and must not be extended upward to reveal more of the legs or body.
"""


def build_dressed_prompt(garment_type: str, mannequin_form: str = "full_front") -> str:
    """Build the dressed-mannequin prompt for a garment type and mannequin form.

    ``mannequin_form`` must match the reference mannequin image: ``"full_front"``, ``"full_side"``,
    ``"top"`` (head to upper hips), ``"bottom"`` (waist to feet), or ``"feet"`` (lower legs and feet).
    """
    if mannequin_form not in FRAMING_BY_FORM:
        raise ValueError(
            f"mannequin_form must be one of {sorted(FRAMING_BY_FORM)}, got {mannequin_form!r}"
        )

    # A neutral bottom only makes sense on a cropped upper-body mannequin, and the
    # footwear guidance only applies to the cropped lower-legs/feet form.
    needs_bottom = mannequin_form == "top"
    needs_footwear = mannequin_form == "feet"
    if needs_bottom:
        extra_guidance = COMPLEMENTARY_BOTTOM_FOR_TOP.format(garment_type=garment_type)
        extra_note = COMPLEMENTARY_BOTTOM_NOTE_FOR_TOP.format(garment_type=garment_type)
    elif needs_footwear:
        extra_guidance = FOOTWEAR_ON_FORM.format(garment_type=garment_type)
        extra_note = FOOTWEAR_ON_FORM_NOTE.format(garment_type=garment_type)
    else:
        extra_guidance = ""
        extra_note = ""
    return prompt_mannequin_dressed_template.format(
        garment_type=garment_type,
        view=VIEW_BY_FORM[mannequin_form],
        view_reference=VIEW_REFERENCE_BY_FORM[mannequin_form],
        framing=FRAMING_BY_FORM[mannequin_form],
        complementary_bottom=extra_guidance,
        complementary_bottom_note=extra_note,
    )


def _detect_mime(data: bytes) -> str:
    """Detect an image's MIME type from its bytes, defaulting to ``image/png``."""
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = (img.format or "").upper()
    except Exception:  # noqa: BLE001 - fall back to a safe default
        return "image/png"
    return {
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
        "BMP": "image/bmp",
    }.get(fmt, "image/png")


def _to_data_url(data: bytes, mime: str | None = None) -> str:
    """Return a ``data:`` URL for the given image bytes.

    The MIME type is detected from the bytes unless one is explicitly given, so
    the declared type always matches the actual image (OpenRouter rejects a
    mismatch with a 400).
    """
    mime = mime or _detect_mime(data)
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _mannequin_reference_path(mannequin_form: str) -> Path:
    """Resolve the reference mannequin image path for a mannequin form."""
    if mannequin_form not in MANNEQUIN_FILE_BY_FORM:
        raise ValueError(
            f"mannequin_form must be one of {sorted(MANNEQUIN_FILE_BY_FORM)}, "
            f"got {mannequin_form!r}"
        )
    return Path(settings.mannequin_dir) / MANNEQUIN_FILE_BY_FORM[mannequin_form]


def polish_clothing_image(
    image_bytes: bytes,
    garment_type: str,
    mannequin_form: str,
    mime_type: str = "image/png",
) -> bytes | None:
    """Dress a studio mannequin in the garment worn by the person in ``image_bytes``.

    Returns the generated PNG bytes, or ``None`` if the API returned no image.
    """
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Configure it in your .env file."
        )

    reference_path = _mannequin_reference_path(mannequin_form)
    if not reference_path.is_file():
        raise FileNotFoundError(f"Mannequin reference image not found: {reference_path}")

    prompt = build_dressed_prompt(garment_type, mannequin_form)

    payload = {
        "model": settings.image_model,
        "prompt": prompt,
        "aspect_ratio": settings.image_aspect_ratio,
        "input_references": [
            {
                "type": "image_url",
                "image_url": {"url": _to_data_url(reference_path.read_bytes())},
            },
            {
                "type": "image_url",
                "image_url": {"url": _to_data_url(image_bytes, mime_type)},
            },
        ],
        "n": 1,
        "output_format": "png",
        "seed": settings.image_seed,
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        OPENROUTER_API_URL, json=payload, headers=headers, timeout=OPENROUTER_TIMEOUT
    )
    response.raise_for_status()
    body = response.json()

    if body.get("error"):
        raise RuntimeError(f"OpenRouter API error: {body['error']}")

    data = body.get("data") or []
    if not data or not data[0].get("b64_json"):
        return None

    return base64.b64decode(data[0]["b64_json"])


# ---------------------------------------------------------------------------
# Virtual try-on (OpenRouter)
# ---------------------------------------------------------------------------

_TRYON_PROMPT = """
Using the uploaded photograph of a person as the subject and the uploaded clothing images as references, dress the person in the outfit composed of the following clothing items:
{clothing_details}

OBJECTIVE:
Present the person wearing the given clothing items so the outfit is immediately readable, while keeping the person's identity and pose intact.

1. GARMENT IDENTIFICATION
* Reproduce each clothing item's exact design: color, fabric, pattern, texture, seams, stitching, hardware, and any logos or prints.
* Do not substitute, restyle, recolor, or redesign any garment.
* Do not add garments that are not part of the given clothing items (no extra layers, belts, or accessories).

2. FIT AND DRAPE
* Dress the person in the given items with a natural fit and drape.
* Match the garment's length: hem position, sleeve length, rise, and inseam.
* Match how each garment sits on the shoulders, chest, waist, hips, and legs.

3. SUBJECT PRESERVATION
* Preserve the subject's face, hair, and hand positions exactly; keep skin texture identical.
* Keep the subject's body proportions and pose unchanged.
* Keep the original lighting and shadows.

4. OUTPUT QUALITY
* High-resolution render with a clean silhouette.
* The outfit is immediately readable from the image alone.
* Suitable as a virtual clothing try-on preview.

IMPORTANT:
The person must wear exactly the given clothing items, with their colors, styles, and patterns preserved.
Footwear items must be worn on the subject's feet and be clearly visible in the final image.
"""


def _build_tryon_prompt(clothings: dict[str, ClothingWithImage]) -> str:
    clothing_details = ""
    for i, (_, clothing) in enumerate(clothings.items(), 1):
        clothing_details += (
            f"Clothing {i} (in image {i}): A {clothing.clothing.color} "
            f"{clothing.clothing.sub_category} ({clothing.clothing.main_category})\n"
        )
    return _TRYON_PROMPT.format(clothing_details=clothing_details)


def generate_fashion_image(
    clothings: dict[str, ClothingWithImage], model_path: str
) -> Image.Image | None:
    """Generate a virtual try-on image and return it as a PIL image."""
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Configure it in your .env file."
        )

    model_file = Path(model_path)
    if not model_file.is_file():
        raise FileNotFoundError(f"Model image not found: {model_file}")

    # The model photo is the subject; each clothing image is a reference.
    input_references = [
        {
            "type": "image_url",
            "image_url": {"url": _to_data_url(model_file.read_bytes())},
        }
    ]
    input_references.extend(
        {
            "type": "image_url",
            "image_url": {"url": _to_data_url(clothing.image_data)},
        }
        for clothing in clothings.values()
        if clothing.image_data
    )

    payload = {
        "model": settings.image_model,
        "prompt": _build_tryon_prompt(clothings),
        "aspect_ratio": settings.image_aspect_ratio,
        "input_references": input_references,
        "n": 1,
        "output_format": "png",
        "seed": settings.image_seed,
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        OPENROUTER_API_URL, json=payload, headers=headers, timeout=OPENROUTER_TIMEOUT
    )
    response.raise_for_status()
    body = response.json()

    if body.get("error"):
        raise RuntimeError(f"OpenRouter API error: {body['error']}")

    data = body.get("data") or []
    if not data or not data[0].get("b64_json"):
        return None

    return Image.open(BytesIO(base64.b64decode(data[0]["b64_json"])))
