"""Clothing-attribute extraction via a local Ollama vision model."""

import base64

from ollama import chat

from closet_muse.domain.schemas import ClothingBase

MODEL = "qwen3-vl:4b"


def extract_clothing_attributes(image_bytes: bytes) -> ClothingBase:
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    response = chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    "Analyze the clothing image and describe the dress "
                    "attributes using the given fields."
                ),
                "images": [encoded_image],
            }
        ],
        format=ClothingBase.model_json_schema(),
        options={"temperature": 0},
    )

    return ClothingBase.model_validate_json(response.message.content)
