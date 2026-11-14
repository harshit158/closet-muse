"""Shared helpers for talking to the OpenRouter API.

Both the image-generation service and the attribute-extraction service send
images to OpenRouter, so the MIME detection and ``data:`` URL encoding live here
instead of being duplicated (or reached for through a private name).
"""

import base64
from io import BytesIO

import requests
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


def _detect_mime(data: bytes) -> str | None:
    """Detect an image's MIME type from its bytes, or ``None`` if unrecognised."""
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = (img.format or "").upper()
    except Exception:  # noqa: BLE001 - not an image PIL can read
        return None
    return _MIME_BY_FORMAT.get(fmt)


def detect_mime(data: bytes) -> str:
    """Detect an image's MIME type from its bytes, defaulting to ``image/png``."""
    return _detect_mime(data) or "image/png"


def to_data_url(data: bytes, mime: str | None = None) -> str:
    """Return a ``data:`` URL for the given image bytes.

    The MIME type is always detected from the bytes; ``mime`` is only a fallback
    for a format PIL cannot identify. Callers cannot be trusted to declare it:
    the frontend labels every upload ``image/png``, so a JPEG photo would be
    declared as PNG and OpenRouter rejects the mismatch with a 400.
    """
    mime = _detect_mime(data) or mime or "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def raise_for_status(response: requests.Response) -> None:
    """Raise ``RuntimeError`` carrying the response body when a request failed.

    ``requests``' own ``raise_for_status`` reports only the status code, but
    OpenRouter puts the real reason in the JSON body (a MIME mismatch, a content
    filter, an unsupported model), so a bare "400 Bad Request" hides the cause.
    """
    if response.ok:
        return
    raise RuntimeError(
        f"OpenRouter request failed with HTTP {response.status_code}: "
        f"{response.text}"
    )
