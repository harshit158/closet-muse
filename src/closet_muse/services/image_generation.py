"""Image generation via OpenRouter (e-commerce polish) and Gemini (virtual try-on).

The onboarding "polish" step dresses a reusable studio mannequin in the garment
worn by the person in the uploaded photo, using the OpenRouter image API
(``meta/muse-image``). The virtual try-on step still uses Google Gemini.
"""

import base64
from io import BytesIO
from pathlib import Path

import requests
from google.genai import types
from PIL import Image

from closet_muse.domain.schemas import ClothingWithImage
from closet_muse.services.gemini import get_client
from closet_muse.settings import settings

MODEL = "gemini-2.5-flash-image"

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
}

# How the reference mannequin image is described in the prompt, per form.
VIEW_REFERENCE_BY_FORM = {
    "full_front": "front-view mannequin image",
    "full_side": "side-view mannequin image",
    "top": "front-view mannequin image",
    "bottom": "front-view mannequin image",
}

# Reference mannequin image filename per form (under ``settings.mannequin_dir``).
MANNEQUIN_FILE_BY_FORM = {
    "full_front": "mannequin_front.png",
    "full_side": "mannequin_side.png",
    "top": "mannequin_top.png",
    "bottom": "mannequin_bottom.png",
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


def build_dressed_prompt(garment_type: str, mannequin_form: str = "full_front") -> str:
    """Build the dressed-mannequin prompt for a garment type and mannequin form.

    ``mannequin_form`` must match the reference mannequin image: ``"full_front"``, ``"full_side"``,
    ``"top"`` (head to upper hips), or ``"bottom"`` (waist to feet).
    """
    if mannequin_form not in FRAMING_BY_FORM:
        raise ValueError(
            f"mannequin_form must be one of {sorted(FRAMING_BY_FORM)}, got {mannequin_form!r}"
        )

    # A neutral bottom only makes sense on a cropped upper-body mannequin.
    needs_bottom = mannequin_form == "top"
    complementary_bottom = (
        COMPLEMENTARY_BOTTOM_FOR_TOP.format(garment_type=garment_type) if needs_bottom else ""
    )
    complementary_bottom_note = (
        COMPLEMENTARY_BOTTOM_NOTE_FOR_TOP.format(garment_type=garment_type) if needs_bottom else ""
    )
    return prompt_mannequin_dressed_template.format(
        garment_type=garment_type,
        view=VIEW_BY_FORM[mannequin_form],
        view_reference=VIEW_REFERENCE_BY_FORM[mannequin_form],
        framing=FRAMING_BY_FORM[mannequin_form],
        complementary_bottom=complementary_bottom,
        complementary_bottom_note=complementary_bottom_note,
    )


def _to_data_url(data: bytes, mime: str = "image/png") -> str:
    """Return a ``data:`` URL for the given image bytes."""
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
# Virtual try-on (Gemini)
# ---------------------------------------------------------------------------

_TRYON_PROMPT = """
Replace the women's outfit with the outfit composed of following clothing items in the given images:
{clothing_details}

Preserve the subject's face, hair and hand positions exactly; keep skin texture identical.
Preserve the colors, styles and patterns in the given clothing items.
Keep original lighting and shadows. Use photorealistic fabric textures.
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
    contents: list[types.Part] = []

    contents.extend(
        types.Part.from_bytes(data=clothing.image_data, mime_type="image/png")
        for clothing in clothings.values()
        if clothing.image_data
    )

    with open(model_path, "rb") as model_file:
        contents.append(types.Part.from_bytes(data=model_file.read(), mime_type="image/png"))

    contents.append(types.Part.from_text(text=_build_tryon_prompt(clothings)))

    response = get_client().models.generate_content(model=MODEL, contents=contents)

    for part in response.candidates[0].content.parts:
        if part.inline_data:
            return Image.open(BytesIO(part.inline_data.data))

    return None
