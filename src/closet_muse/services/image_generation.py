"""Image generation via the OpenRouter image API.

Two flows use the same API, each with its own configurable model
(``settings.image_model_polish`` and ``settings.image_model_tryon``):

* the onboarding "polish" step dresses a reusable studio mannequin in the garment
  worn by the person in the uploaded photo; and
* the outfit generator dresses a model in the selected wardrobe items (virtual try-on).
"""

import base64
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from closet_muse.domain.schemas import ClothingWithImage
from closet_muse.services.openrouter import require_api_key, to_data_url
from closet_muse.settings import settings

# ---------------------------------------------------------------------------
# Dressed-mannequin prompt (ported from notebooks/open_ai_image_model.ipynb)
# ---------------------------------------------------------------------------

prompt_mannequin_dressed_template = """
Using the uploaded photograph of a real person and the uploaded {view_reference} as references, dress the mannequin in the {garment_type} worn by the person in the photograph, reproducing the exact fit of that garment.{photo_guidance}

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
# The crop is identical for the front and tilted views of a form, so it is keyed
# by form only.
FRAMING_BY_FORM = {
    "full": "Show the complete mannequin from head to feet, exactly as framed in the uploaded mannequin image.",
    "face": (
        "Show only the head, neck, and shoulders, exactly as cropped in the uploaded "
        "mannequin image. Do not extend the crop downward, and do not add a chest, torso, "
        "arms, or legs."
    ),
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

# Camera view per (form, view), so the output matches the reference image's orientation.
VIEW_BY_FORM_AND_VIEW = {
    ("full", "front"): "Straight-on front view, matching the uploaded mannequin image.",
    ("full", "tilted"): (
        "Three-quarter view, matching the uploaded mannequin image: the body is turned about "
        "30 degrees away from the front. Do not render a straight-on front view or a full "
        "side profile."
    ),
    ("face", "front"): "Straight-on front view, matching the uploaded mannequin image.",
    ("face", "tilted"): (
        "Three-quarter view, matching the uploaded mannequin image: the head and shoulders are "
        "turned about 30 degrees away from the front, with the face still visible. Do not "
        "render a straight-on front view or a full side profile."
    ),
    ("top", "front"): "Straight-on front view, matching the uploaded mannequin image.",
    ("top", "tilted"): (
        "Three-quarter view, matching the uploaded mannequin image: the upper body is turned "
        "about 30 degrees away from the front. Do not render a straight-on front view or a "
        "full side profile."
    ),
    ("bottom", "front"): "Straight-on front view, matching the uploaded mannequin image.",
    ("bottom", "tilted"): (
        "Three-quarter view, matching the uploaded mannequin image: the lower body is turned "
        "about 30 degrees away from the front. Do not render a straight-on front view or a "
        "full side profile."
    ),
    ("feet", "front"): "Straight-on front view, matching the uploaded mannequin image.",
    ("feet", "tilted"): (
        "Three-quarter view, matching the uploaded mannequin image: the lower legs and feet are "
        "turned about 30 degrees away from the front. Do not render a straight-on front view "
        "or a full side profile."
    ),
}

# How the reference mannequin image is described in the prompt, per (form, view).
VIEW_REFERENCE_BY_FORM_AND_VIEW = {
    (form, "front"): "front-view mannequin image" for form in FRAMING_BY_FORM
} | {
    (form, "tilted"): "three-quarter-view mannequin image" for form in FRAMING_BY_FORM
}

# Added to the prompt when the person's garment is supplied as several photos
# (a primary shot plus additional angles or close-ups) in the same request.
MULTI_PHOTO_GUIDANCE = (
    "\n\nThe person's {garment_type} appears in several uploaded photographs: one primary "
    "photo plus additional angles or close-ups. Treat every photo as the same single garment "
    "and use them together to read its exact design, color, material, and fit. If the photos "
    "disagree on a detail, prefer the primary photo for overall fit and the close-ups for "
    "fabric, pattern, and construction details."
)

# Reference mannequin image filename per (form, view) (under ``settings.mannequin_dir``).
MANNEQUIN_FILE_BY_FORM_AND_VIEW = {
    (form, view): f"mannequin_{form}{'' if view == 'front' else '_tilted'}.png"
    for form in FRAMING_BY_FORM
    for view in ("front", "tilted")
}

# The mannequin forms offered for onboarding, in display order.
MANNEQUIN_FORMS = tuple(FRAMING_BY_FORM)
# The two perspectives generated for every form.
MANNEQUIN_VIEWS = ("front", "tilted")

# When the focus garment is a top on a CROPPED (upper-body) mannequin, the mannequin also
# wears a plain, neutral bottom so it does not look unfinished - but ONLY within the
# existing crop. The frame must NOT be extended downward to reveal more of the bottom.
COMPLEMENTARY_BOTTOM_FOR_TOP = """* The mannequin must not be left bare below the waist: dress it in a plain, neutral-colored simple legging (light grey, beige, or off-white), so the form looks complete.
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

# When the focus item is an accessory on the CROPPED (head, neck and shoulders)
# mannequin, the accessory must be worn in its natural place so it reads clearly.
ACCESSORY_ON_FACE_FORM = """* The display form must be shown wearing the {garment_type} in its natural position: a hat or cap on the head, sunglasses on the face, earrings on the ears, a necklace or scarf around the neck, and a shawl over the shoulders.
* The {garment_type} is the subject and must be fully visible and clearly readable.
* Reproduce the exact design: color, material, texture, pattern, shape, hardware, stitching, and any logos or prints.
* Do not substitute, restyle, recolor, or redesign the {garment_type}.
* Do not add any other item to the form (no clothing, jewelry, or accessories) beyond what the uploaded photograph shows.
* Do not show the form without the {garment_type} worn.
"""

ACCESSORY_ON_FACE_FORM_NOTE = """The {garment_type} must be worn on the display form in its natural position and must be the clearly visible subject.
The form must stay within the existing crop: the frame must end exactly where the uploaded mannequin image ends, and must not be extended downward to reveal the chest, torso, or arms.
"""


def build_dressed_prompt(
    garment_type: str,
    mannequin_form: str = "full",
    num_photos: int = 1,
    view: str = "front",
) -> str:
    """Build the dressed-mannequin prompt for a garment type, form, and view.

    ``mannequin_form`` must match the reference mannequin image: ``"full"``,
    ``"face"`` (head, neck and shoulders), ``"top"`` (head to upper hips),
    ``"bottom"`` (waist to feet), or ``"feet"`` (lower legs and feet).
    ``view`` is ``"front"`` or ``"tilted"`` (three-quarter) and must match the
    reference image's orientation.
    ``num_photos`` is the number of photos of the person's garment supplied as references;
    when more than one is given, the prompt explains that they show the same garment.
    """
    if mannequin_form not in FRAMING_BY_FORM:
        raise ValueError(
            f"mannequin_form must be one of {sorted(FRAMING_BY_FORM)}, got {mannequin_form!r}"
        )
    if view not in MANNEQUIN_VIEWS:
        raise ValueError(
            f"view must be one of {list(MANNEQUIN_VIEWS)}, got {view!r}"
        )

    # A neutral bottom only makes sense on a cropped upper-body mannequin, the
    # footwear guidance only applies to the cropped lower-legs/feet form, and the
    # accessory guidance only applies to the cropped head/neck/shoulders form.
    if mannequin_form == "top":
        extra_guidance = COMPLEMENTARY_BOTTOM_FOR_TOP.format(garment_type=garment_type)
        extra_note = COMPLEMENTARY_BOTTOM_NOTE_FOR_TOP.format(garment_type=garment_type)
    elif mannequin_form == "feet":
        extra_guidance = FOOTWEAR_ON_FORM.format(garment_type=garment_type)
        extra_note = FOOTWEAR_ON_FORM_NOTE.format(garment_type=garment_type)
    elif mannequin_form == "face":
        extra_guidance = ACCESSORY_ON_FACE_FORM.format(garment_type=garment_type)
        extra_note = ACCESSORY_ON_FACE_FORM_NOTE.format(garment_type=garment_type)
    else:
        extra_guidance = ""
        extra_note = ""
    photo_guidance = (
        MULTI_PHOTO_GUIDANCE.format(garment_type=garment_type) if num_photos > 1 else ""
    )
    return prompt_mannequin_dressed_template.format(
        garment_type=garment_type,
        view=VIEW_BY_FORM_AND_VIEW[(mannequin_form, view)],
        view_reference=VIEW_REFERENCE_BY_FORM_AND_VIEW[(mannequin_form, view)],
        framing=FRAMING_BY_FORM[mannequin_form],
        complementary_bottom=extra_guidance,
        complementary_bottom_note=extra_note,
        photo_guidance=photo_guidance,
    )


def _mannequin_reference_path(mannequin_form: str, view: str = "front") -> Path:
    """Resolve the reference mannequin image path for a form and view."""
    key = (mannequin_form, view)
    if key not in MANNEQUIN_FILE_BY_FORM_AND_VIEW:
        raise ValueError(
            f"mannequin_form/view must be one of "
            f"{sorted(MANNEQUIN_FILE_BY_FORM_AND_VIEW)}, got {key!r}"
        )
    return Path(settings.mannequin_dir) / MANNEQUIN_FILE_BY_FORM_AND_VIEW[key]


def _polish_one_view(
    *,
    image_list: list[bytes],
    mime_list: list[str | None],
    garment_type: str,
    mannequin_form: str,
    view: str,
) -> bytes | None:
    """Dress one mannequin view in the garment and return the PNG bytes."""
    reference_path = _mannequin_reference_path(mannequin_form, view)
    if not reference_path.is_file():
        raise FileNotFoundError(f"Mannequin reference image not found: {reference_path}")

    prompt = build_dressed_prompt(
        garment_type, mannequin_form, num_photos=len(image_list), view=view
    )

    payload = {
        "model": settings.image_model_polish,
        "prompt": prompt,
        "aspect_ratio": settings.image_aspect_ratio,
        "input_references": [
            {
                "type": "image_url",
                "image_url": {"url": to_data_url(reference_path.read_bytes())},
            },
            *(
                {
                    "type": "image_url",
                    "image_url": {"url": to_data_url(image, mime)},
                }
                for image, mime in zip(image_list, mime_list)
            ),
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
        settings.openrouter_image_url,
        json=payload,
        headers=headers,
        timeout=settings.image_timeout,
    )
    response.raise_for_status()
    body = response.json()

    if body.get("error"):
        raise RuntimeError(f"OpenRouter API error: {body['error']}")

    data = body.get("data") or []
    if not data or not data[0].get("b64_json"):
        return None

    return base64.b64decode(data[0]["b64_json"])


def polish_clothing_image(
    images: bytes | Sequence[bytes],
    garment_type: str,
    mannequin_form: str,
    mime_types: Sequence[str] | str | None = None,
) -> dict[str, bytes]:
    """Dress a studio mannequin in the garment worn by the person in the photo(s).

    The garment is applied to BOTH perspectives of the chosen form - the
    straight-on front view and the three-quarter tilted view - so the try-on
    generator can read the garment from two angles. The two requests run
    concurrently.

    ``images`` accepts a single photo or several photos of the *same* garment
    (a primary shot plus additional angles); every photo is attached as a
    reference so the model can read the garment from all angles.

    ``mime_types`` may be a single MIME type or one per image; when omitted the
    MIME type is detected from each image's bytes.

    Returns ``{"front": png_bytes, "tilted": png_bytes}``. Raises
    ``RuntimeError`` if either view came back without an image, so a partially
    dressed item is never stored.
    """
    require_api_key()

    # Accept a lone bytes object as well as a sequence, and normalise the MIME types.
    image_list: list[bytes] = [bytes(images)] if isinstance(images, (bytes, bytearray)) else [bytes(i) for i in images]
    if not image_list:
        raise ValueError("At least one image is required to polish a garment.")

    if mime_types is None:
        mime_list: list[str | None] = [None] * len(image_list)
    elif isinstance(mime_types, str):
        mime_list = [mime_types] * len(image_list)
    else:
        mime_list = list(mime_types)
        if len(mime_list) != len(image_list):
            raise ValueError(
                "mime_types must have the same length as images "
                f"({len(mime_list)} != {len(image_list)})"
            )

    # Fail fast on a missing reference before spending an API call.
    for view in MANNEQUIN_VIEWS:
        reference_path = _mannequin_reference_path(mannequin_form, view)
        if not reference_path.is_file():
            raise FileNotFoundError(
                f"Mannequin reference image not found: {reference_path}"
            )

    def _run(view: str) -> bytes | None:
        return _polish_one_view(
            image_list=image_list,
            mime_list=mime_list,
            garment_type=garment_type,
            mannequin_form=mannequin_form,
            view=view,
        )

    # Both views are independent requests, so run them concurrently.
    with ThreadPoolExecutor(max_workers=len(MANNEQUIN_VIEWS)) as executor:
        futures = {view: executor.submit(_run, view) for view in MANNEQUIN_VIEWS}
        results = {view: future.result() for view, future in futures.items()}

    missing = [view for view, data in results.items() if not data]
    if missing:
        raise RuntimeError(
            f"Image generation returned no image for the {', '.join(missing)} view."
        )

    return {view: data for view, data in results.items() if data is not None}


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
* When an item is shown in more than one image, those images are the SAME garment on the same mannequin from different angles (a straight-on front view and a three-quarter view). Use both together to read its exact shape, volume, and how the fabric hangs, and reproduce that same fit on the person.

3. SUBJECT PRESERVATION
* Preserve the subject's face, hair, and hand positions exactly; keep skin texture identical.
* Keep the subject's body proportions and pose unchanged.
* The subject photograph may be a straight-on front view or a three-quarter view. Keep the subject's exact camera angle and body orientation: a three-quarter view must stay a three-quarter view, and a front view must stay a front view.
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
    """Describe each clothing item and which reference images show it.

    Image 1 is always the subject photo, so clothing references start at image 2.
    An item with a tilted image occupies two consecutive reference slots.
    """
    clothing_details = ""
    image_number = 2  # image 1 is the person
    for i, (_, clothing) in enumerate(clothings.items(), 1):
        if clothing.image_data_tilted:
            images = f"images {image_number} and {image_number + 1}"
            image_number += 2
        else:
            images = f"image {image_number}"
            image_number += 1
        clothing_details += (
            f"Clothing {i} (in {images}): A {clothing.clothing.color} "
            f"{clothing.clothing.sub_category} ({clothing.clothing.main_category})\n"
        )
    return _TRYON_PROMPT.format(clothing_details=clothing_details)


def _tryon_one_view(
    clothings: dict[str, ClothingWithImage], model_path: str
) -> bytes | None:
    """Dress one model view in the outfit and return the PNG bytes."""
    model_file = Path(model_path)
    if not model_file.is_file():
        raise FileNotFoundError(f"Model image not found: {model_file}")

    # The model photo is the subject; each clothing image is a reference. Items
    # onboarded with a tilted image contribute BOTH perspectives, so the model
    # can read the garment's fit and drape from two angles.
    input_references = [
        {
            "type": "image_url",
            "image_url": {"url": to_data_url(model_file.read_bytes())},
        }
    ]
    for clothing in clothings.values():
        for data in (clothing.image_data, clothing.image_data_tilted):
            if data:
                input_references.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": to_data_url(data)},
                    }
                )

    payload = {
        "model": settings.image_model_tryon,
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
        settings.openrouter_image_url,
        json=payload,
        headers=headers,
        timeout=settings.image_timeout,
    )
    response.raise_for_status()
    body = response.json()

    if body.get("error"):
        raise RuntimeError(f"OpenRouter API error: {body['error']}")

    data = body.get("data") or []
    if not data or not data[0].get("b64_json"):
        return None

    return base64.b64decode(data[0]["b64_json"])


def generate_fashion_images(
    clothings: dict[str, ClothingWithImage], model_paths: dict[str, str]
) -> dict[str, bytes]:
    """Generate one virtual try-on image per model view.

    ``model_paths`` maps a view name (``"left"``, ``"center"``, ``"right"``) to
    the model photograph used as the subject for that view. Each view is an
    independent request, so they run concurrently and the pose of each subject
    photograph is preserved in its own output.

    Returns ``{view_name: png_bytes}``. Raises ``RuntimeError`` if any view came
    back without an image, so a partial set of looks is never stored.
    """
    require_api_key()
    if not model_paths:
        raise ValueError("At least one model view is required to generate an outfit.")

    # Fail fast on a missing subject before spending any API calls.
    for view, model_path in model_paths.items():
        if not Path(model_path).is_file():
            raise FileNotFoundError(
                f"Model image for the {view} view not found: {model_path}"
            )

    def _run(model_path: str) -> bytes | None:
        return _tryon_one_view(clothings, model_path)

    # The views are independent requests, so run them concurrently.
    with ThreadPoolExecutor(max_workers=len(model_paths)) as executor:
        futures = {
            view: executor.submit(_run, model_path)
            for view, model_path in model_paths.items()
        }
        results = {view: future.result() for view, future in futures.items()}

    missing = [view for view, data in results.items() if not data]
    if missing:
        raise RuntimeError(
            f"Image generation returned no image for the {', '.join(missing)} view."
        )

    return {view: data for view, data in results.items() if data is not None}
