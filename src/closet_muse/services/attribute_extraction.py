"""Clothing-attribute extraction via a local Ollama vision model."""

import base64
from collections.abc import Sequence

import ollama

from closet_muse.domain.schemas import ClothingBase
from closet_muse.settings import settings

_PROMPT_SINGLE = (
    "Analyze the clothing image and describe the dress "
    "attributes using the given fields."
)

_PROMPT_MULTIPLE = (
    "Using the {count} uploaded photos of the same clothing item taken from "
    "different angles, analyze the garment and describe its dress attributes "
    "using the given fields. Treat every photo as the same single item and "
    "combine the evidence from all angles."
)


def extract_clothing_attributes(images: Sequence[bytes]) -> ClothingBase:
    """Extract clothing attributes from one or more photos of the same garment.

    When several photos are given they are treated as different angles of a
    single item, and the model is asked to combine evidence from all of them.
    """
    if not images:
        raise ValueError("At least one image is required to extract attributes.")

    encoded_images = [base64.b64encode(image).decode("utf-8") for image in images]
    prompt = (
        _PROMPT_SINGLE
        if len(images) == 1
        else _PROMPT_MULTIPLE.format(count=len(images))
    )

    # ``ollama.chat`` talks to the default host; an explicit client is only needed
    # when a custom host is configured.
    client = ollama.Client(host=settings.ollama_host) if settings.ollama_host else ollama
    response = client.chat(
        model=settings.attribute_model,
        messages=[
            {
                "role": "user",
                "content": prompt,
                "images": encoded_images,
            }
        ],
        format=ClothingBase.model_json_schema(),
        options={"temperature": 0},
    )

    return ClothingBase.model_validate_json(response.message.content)
