"""Image generation via Google Gemini (e-commerce polish + virtual try-on)."""

from io import BytesIO

from google.genai import types
from PIL import Image

from closet_muse.domain.schemas import ClothingWithImage
from closet_muse.services.gemini import get_client

MODEL = "gemini-2.5-flash-image"

_POLISH_PROMPT = """Create a professional and polished photo of the dress for an e-commerce fashion store.
Take the dress from the first image and polish it up so that it can be posted on e-commerce fashion store.
Background should be white.
"""

_TRYON_PROMPT = """
Replace the women's outfit with the outfit composed of following clothing items in the given images:
{clothing_details}

Preserve the subject's face, hair and hand positions exactly; keep skin texture identical.
Preserve the colors, styles and patterns in the given clothing items.
Keep original lighting and shadows. Use photorealistic fabric textures.
"""


def polish_clothing_image(image_bytes: bytes) -> bytes | None:
    """Return a polished (white-background) version of a clothing image."""
    response = get_client().models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            types.Part.from_text(text=_POLISH_PROMPT),
        ],
    )

    if (
        response.candidates
        and response.candidates[0].content
        and response.candidates[0].content.parts
    ):
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return part.inline_data.data
    return None


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
