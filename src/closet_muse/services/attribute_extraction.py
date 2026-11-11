"""Clothing-attribute extraction via an OpenRouter vision model.

The model is asked for a JSON object that matches ``ClothingBase``, and the
request uses OpenRouter's structured outputs (``response_format`` with a JSON
schema) so the reply is schema-conforming instead of free-form text that has to
be parsed defensively.
"""

from collections.abc import Sequence
from typing import Any

import requests

from closet_muse.domain import enums
from closet_muse.domain.schemas import ClothingBase
from closet_muse.services.openrouter import require_api_key, to_data_url
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

# Appended to every prompt: the schema marks every field as required, so the
# model must be told what to do when the photo does not show a detail.
_FIELD_GUIDANCE = (
    " Fill in every field. Use null for a field the photos do not show, and do "
    "not guess a brand, size, or material that is not visible."
)

# Fields that describe stored files rather than the garment itself, so they are
# never part of the extraction schema.
_NON_EXTRACTABLE_FIELDS = frozenset({"image_path", "image_path_tilted"})

_SCHEMA_NAME = "clothing_attributes"


def _simplify(node: Any, defs: dict[str, Any]) -> Any:
    """Inline ``$ref``s and drop ``default`` keys from a JSON schema fragment.

    Pydantic emits enums as ``{"$ref": "#/$defs/Material"}`` plus a top-level
    ``$defs`` block. Inlining them keeps the schema self-contained (no dangling
    references once ``$defs`` is dropped) and avoids relying on each provider's
    support for ``$ref``. ``default`` is not part of the strict subset.
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            target = defs.get(ref.removeprefix("#/$defs/"), {})
            # Keep any sibling keys (e.g. a description) alongside the target.
            merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
            return _simplify(merged, defs)
        return {
            key: _simplify(value, defs)
            for key, value in node.items()
            if key != "default"
        }
    if isinstance(node, list):
        return [_simplify(item, defs) for item in node]
    return node


def _extraction_schema(
    main_category: enums.WomenClothingMainCategory | None = None,
) -> dict[str, Any]:
    """Build the strict JSON schema for the extraction response.

    Derived from ``ClothingBase`` so the field descriptions and the enum values
    stay in one place. Strict mode requires every property to be listed in
    ``required`` and forbids extra properties, so the optional fields are made
    required-but-nullable (the model returns ``null`` when it cannot tell).

    When ``main_category`` is given (the garment type the user picked), both
    category fields are pinned to it: ``main_category`` to that single value and
    ``sub_category`` to that category's sub-enum. Without this the model can
    return a pair that disagrees (e.g. ``Bottoms`` + ``Dresses``) or a
    sub-category that does not exist for the category, which the form's
    selectbox then silently drops.
    """
    model_schema = ClothingBase.model_json_schema()
    defs = model_schema.get("$defs", {})
    properties = {
        name: _simplify(definition, defs)
        for name, definition in model_schema.get("properties", {}).items()
        if name not in _NON_EXTRACTABLE_FIELDS
    }

    if main_category is not None:
        properties["main_category"] = {
            "type": "string",
            "enum": [main_category.value],
            "description": "The category of the item.",
        }
        sub_categories = [
            member.value for member in enums.CATEGORY_MAPPING.get(main_category, [])
        ]
        if sub_categories:
            properties["sub_category"] = {
                "anyOf": [
                    {"type": "string", "enum": sub_categories},
                    {"type": "null"},
                ],
                "description": (
                    "The specific type of item within the category, or null if "
                    "none of the options fit."
                ),
            }

    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _build_prompt(count: int) -> str:
    """The instruction text for a single photo or several angles of one item."""
    prompt = _PROMPT_SINGLE if count == 1 else _PROMPT_MULTIPLE.format(count=count)
    return prompt + _FIELD_GUIDANCE


def _build_payload(
    images: Sequence[bytes],
    main_category: enums.WomenClothingMainCategory | None = None,
) -> dict[str, Any]:
    """The Chat Completions request body for the given photos."""
    # The text part goes first: OpenRouter parses the content in order, and the
    # instruction reads better before the images it refers to.
    content: list[dict[str, Any]] = [
        {"type": "text", "text": _build_prompt(len(images))}
    ]
    content.extend(
        {"type": "image_url", "image_url": {"url": to_data_url(image)}}
        for image in images
    )

    return {
        "model": settings.attribute_model,
        "messages": [{"role": "user", "content": content}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": _SCHEMA_NAME,
                "strict": True,
                "schema": _extraction_schema(main_category),
            },
        },
        # Only route to providers that support every parameter above, so the
        # schema is enforced rather than silently ignored.
        "provider": {"require_parameters": True},
        "temperature": 0,
    }


def _post(payload: dict[str, Any]) -> dict[str, Any]:
    """POST the payload and return the parsed response body."""
    response = requests.post(
        settings.openrouter_chat_url,
        json=payload,
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        timeout=settings.attribute_timeout,
    )
    if not response.ok:
        # Include the body: OpenRouter puts the real reason (unsupported model,
        # schema rejected, ...) in it, and a bare status code hides that.
        raise RuntimeError(
            f"OpenRouter attribute extraction failed with HTTP "
            f"{response.status_code}: {response.text}"
        )

    body = response.json()
    if body.get("error"):
        raise RuntimeError(f"OpenRouter API error: {body['error']}")
    return body


def extract_clothing_attributes(
    images: Sequence[bytes],
    main_category: enums.WomenClothingMainCategory | None = None,
) -> ClothingBase:
    """Extract clothing attributes from one or more photos of the same garment.

    When several photos are given they are treated as different angles of a
    single item, and the model is asked to combine evidence from all of them.

    ``main_category`` is the garment type the user already chose. When given,
    the schema pins the category and restricts ``sub_category`` to that
    category's options, so the result always fits the form.
    """
    if not images:
        raise ValueError("At least one image is required to extract attributes.")
    require_api_key()

    body = _post(_build_payload(images, main_category))

    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter returned no choices for attribute extraction.")

    choice = choices[0]
    if choice.get("finish_reason") == "length":
        raise RuntimeError(
            "Attribute extraction was truncated before the JSON was complete."
        )

    content = (choice.get("message") or {}).get("content")
    if not content:
        raise RuntimeError("OpenRouter returned an empty attribute extraction.")

    return ClothingBase.model_validate_json(content)
