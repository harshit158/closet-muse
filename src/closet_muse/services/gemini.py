"""Lazily-constructed Google Gemini client.

The client is created on first use so that importing application modules never
requires a ``GEMINI_API_KEY`` or triggers network setup.
"""

from functools import lru_cache

from google import genai

from closet_muse.settings import settings


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Configure it in your .env file."
        )
    return genai.Client(api_key=settings.gemini_api_key)
