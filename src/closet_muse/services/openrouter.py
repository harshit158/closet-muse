"""Shared helpers for talking to the OpenRouter API.

Both the image-generation service and the attribute-extraction service send
images to OpenRouter, so the MIME detection and ``data:`` URL encoding live here
instead of being duplicated (or reached for through a private name).
"""

import base64
from io import BytesIO

from PIL import Image

from closet_muse.settings import settings

# Image formats OpenRouter accepts as input, keyed by the format PIL reports.
_MIME_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "JPG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "BMP": "image/bmp",
}


def require_api_key() -> None:
    """Raise ``RuntimeError`` when no OpenRouter API key is configured."""
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Configure it in your .env file."
        )


def detect_mime(data: bytes) -> str:
    """Detect an image's MIME type from its bytes, defaulting to ``image/png``."""
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = (img.format or "").upper()
    except Exception:  # noqa: BLE001 - fall back to a safe default
        return "image/png"
    return _MIME_BY_FORMAT.get(fmt, "image/png")


def to_data_url(data: bytes, mime: str | None = None) -> str:
    """Return a ``data:`` URL for the given image bytes.

    The MIME type is detected from the bytes unless one is explicitly given, so
    the declared type always matches the actual image (OpenRouter rejects a
    mismatch with a 400).
    """
    mime = mime or detect_mime(data)
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
