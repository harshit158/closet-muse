"""HTTP client for the Closet Muse backend.

The frontend talks to the backend exclusively through this module — it must
never import ``closet_muse.db`` or ``closet_muse.services``.
"""

from dataclasses import dataclass, field
from io import BytesIO
from typing import Protocol
import zipfile

import requests

from closet_muse.domain.enums import WomenClothingMainCategory
from closet_muse.domain.schemas import ClothingBase, ClothingUpdate
from closet_muse.settings import settings

TIMEOUT = 300


class FileLike(Protocol):
    """The minimal file interface the upload endpoints need.

    Both Streamlit's ``UploadedFile`` and ``NamedBytesIO`` satisfy this.
    """

    name: str
    type: str

    def getvalue(self) -> bytes: ...


class NamedBytesIO(BytesIO):
    """BytesIO carrying ``name`` and ``type`` so it can be uploaded like a file."""

    def __init__(self, data: bytes, name: str, type: str = "image/png") -> None:  # noqa: A002
        super().__init__(data)
        self.name = name
        self.type = type


@dataclass
class GeneratedOutfit:
    """A generated look: the persisted outfit id plus one PNG per model view.

    ``outfit_id`` is ``None`` only if the backend omitted the header, which would
    mean the outfit was not persisted — the views are still usable for display.

    ``credits_remaining`` is the balance after the spend, read from the
    ``X-Credits-Remaining`` header. ``None`` when the backend did not report it, so a
    caller can tell "unknown" apart from "zero".
    """

    outfit_id: str | None
    views: dict[str, bytes] = field(default_factory=dict)
    credits_remaining: int | None = None


class InsufficientCreditsError(Exception):
    """Raised when the backend refuses a generation because the balance is too low."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _post(path: str, **kwargs) -> requests.Response:
    return requests.post(f"{settings.backend_url}{path}", timeout=TIMEOUT, **kwargs)


def _get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{settings.backend_url}{path}", timeout=TIMEOUT, **kwargs)


def _patch(path: str, **kwargs) -> requests.Response:
    return requests.patch(f"{settings.backend_url}{path}", timeout=TIMEOUT, **kwargs)


def _delete(path: str, **kwargs) -> requests.Response:
    return requests.delete(f"{settings.backend_url}{path}", timeout=TIMEOUT, **kwargs)


def polish_clothing_image(
    images: list[FileLike],
    garment_type: str,
    mannequin_form: str,
    garment_description: str | None = None,
) -> dict[str, bytes]:
    """Dress both mannequin perspectives in the garment.

    ``garment_description`` is the optional free-text wording the user supplied
    (e.g. "white linen button-down shirt"). It narrows the garment type down to
    the one piece to transfer and is omitted from the request when empty.

    The backend returns a ZIP archive holding one PNG per view, so this unpacks
    it into ``{"front": bytes, "tilted": bytes}``. Raises ``requests.HTTPError``
    on a failed request and ``ValueError`` if the archive is missing a view.
    """
    files = [("files", (image.name, image.getvalue(), image.type)) for image in images]
    data = {"garment_type": garment_type, "mannequin_form": mannequin_form}
    # Strip so whitespace-only input is treated as "no description" rather than
    # sending a blank field the backend would then have to ignore.
    description = (garment_description or "").strip()
    if description:
        data["garment_description"] = description
    response = _post("/images/polish/", files=files, data=data)
    response.raise_for_status()

    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        views = {
            name.removesuffix(".png"): archive.read(name)
            for name in archive.namelist()
            if name.endswith(".png")
        }

    missing = {"front", "tilted"} - views.keys()
    if missing:
        raise ValueError(
            f"Polish response is missing the {', '.join(sorted(missing))} view."
        )
    return views


def generate_clothing_attributes(
    images: list[FileLike],
    main_category: WomenClothingMainCategory | None = None,
    garment_hint: str | None = None,
) -> ClothingBase:
    """Extract clothing attributes from the uploaded photos.

    ``main_category`` is the garment type the user already selected; when given,
    the backend constrains the category and sub-category to it, so the result
    always fits the form.

    ``garment_hint`` is the optional free-text description of the exact piece.
    When given, the extractor is told to analyse that garment rather than any
    other one visible in the photos.

    Raises ``requests.HTTPError`` on a failed request so the caller can surface
    the failure; extraction is a user-triggered step of its own.
    """
    files = [("files", (image.name, image.getvalue(), image.type)) for image in images]
    data = {"main_category": main_category.value} if main_category else {}
    # Strip so whitespace-only input is treated as "no hint" rather than sending a
    # blank field the backend would then have to ignore.
    hint = (garment_hint or "").strip()
    if hint:
        data["garment_hint"] = hint
    response = _post("/images/attributes/", files=files, data=data or None)
    response.raise_for_status()
    return ClothingBase(**response.json())


def upload_image(bucket: str, file: FileLike) -> str:
    files = {"file": (file.name, file.getvalue(), file.type)}
    response = _post(f"/images/upload/{bucket}/", files=files)
    response.raise_for_status()
    return response.json()["image_path"]


def fetch_image(bucket: str, filename: str) -> bytes:
    response = _get(f"/images/{bucket}/{filename}")
    response.raise_for_status()
    return response.content


def add_clothing_item(
    user_id: int,
    clothing: ClothingBase,
    image: FileLike,
    image_tilted: FileLike | None = None,
    source_images: list[FileLike] | None = None,
) -> dict:
    """Create a wardrobe item, uploading its polished views and original photos.

    ``image`` / ``image_tilted`` are the polished mannequin renders (``front`` and
    ``tilted``); ``image_tilted`` is optional so an item can still be saved with a
    single perspective. ``source_images`` are the user's own uploads, kept so the
    item can be re-polished later — they are stored in their own bucket.

    ``clothing.mannequin_form`` (when set) is recorded as provenance, so the item
    can be re-polished or debugged against the form it was generated on.
    """
    # Upload first, then attach the returned filenames to the record.
    images = [
        {
            "view": "front",
            "image_path": upload_image(settings.storage_bucket_clothing, image),
        }
    ]
    if image_tilted is not None:
        images.append(
            {
                "view": "tilted",
                "image_path": upload_image(
                    settings.storage_bucket_clothing, image_tilted
                ),
            }
        )

    payload = clothing.model_dump(mode="json")
    payload["images"] = images
    payload["source_image_paths"] = [
        upload_image(settings.storage_bucket_clothing_source, photo)
        for photo in (source_images or [])
    ]

    response = _post(f"/clothing/{user_id}", json=payload)
    response.raise_for_status()
    return response.json()


def fetch_clothing_images(clothing_id: str) -> list[dict]:
    """Fetch a garment's polished renders (one row per mannequin view)."""
    response = _get(f"/clothing/item/{clothing_id}/images")
    response.raise_for_status()
    return response.json()


def fetch_clothing_source_images(clothing_id: str) -> list[dict]:
    """Fetch a garment's original upload photos, in upload order."""
    response = _get(f"/clothing/item/{clothing_id}/source-images")
    response.raise_for_status()
    return response.json()


def update_clothing_item(clothing_id: str, clothing: ClothingUpdate) -> dict:
    """Update the provided fields of a wardrobe item (partial update)."""
    payload = clothing.model_dump(mode="json", exclude_unset=True)
    response = _patch(f"/clothing/item/{clothing_id}", json=payload)
    response.raise_for_status()
    return response.json()


def delete_clothing_item(clothing_id: str) -> dict:
    """Delete a wardrobe item and its stored image."""
    response = _delete(f"/clothing/item/{clothing_id}")
    response.raise_for_status()
    return response.json()


def list_clothing(
    user_id: int, main_category: WomenClothingMainCategory | None = None
) -> list[dict]:
    params = {}
    if main_category is not None:
        params["main_category"] = main_category.value
    response = _get(f"/clothing/{user_id}", params=params)
    response.raise_for_status()
    return response.json()


def clothing_counts(user_id: int) -> dict[str, int]:
    """Get the counts of clothing items for a specific user."""
    response = _get(f"/clothing/counts/{user_id}")
    response.raise_for_status()
    return response.json()


def generate_outfit(
    user_id: int, clothing_ids: list[str]
) -> "GeneratedOutfit | None":
    """Generate one outfit image per model view for the given clothing IDs.

    The backend returns a ZIP archive holding one PNG per model view, so this
    unpacks it into ``{"left": bytes, "center": bytes, "right": bytes}``. The
    outfit is persisted server-side, and its id comes back in the ``X-Outfit-Id``
    header (the body is binary, so it cannot carry it). The balance left after the
    spend comes back in ``X-Credits-Remaining``.

    Raises :class:`InsufficientCreditsError` when the backend answers ``402``, so the
    view can show a specific message instead of a generic failure. Returns ``None`` on
    any other failed or empty response.
    """
    response = _post(
        f"/outfits/generate/{user_id}",
        json={"clothing_ids": clothing_ids},
    )
    if response.status_code == 402:
        detail = "Not enough credits to generate an outfit."
        try:
            detail = response.json().get("detail", detail)
        except ValueError:
            pass
        raise InsufficientCreditsError(detail)
    if response.status_code != 200 or not response.content:
        return None

    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        views = {
            name.removesuffix(".png"): archive.read(name)
            for name in archive.namelist()
            if name.endswith(".png")
        }

    remaining = response.headers.get("X-Credits-Remaining")
    return GeneratedOutfit(
        outfit_id=response.headers.get("X-Outfit-Id"),
        views=views,
        credits_remaining=int(remaining) if remaining is not None else None,
    )


def fetch_outfit_history(user_id: int) -> list[dict]:
    """List a user's saved outfits, newest first."""
    response = _get(f"/outfits/{user_id}/history")
    response.raise_for_status()
    return response.json()


def fetch_outfit_images(outfit_id: str) -> list[dict]:
    """Fetch the persisted renders for one outfit.

    Rows come back unordered; order them against ``settings.model_image_views``.
    """
    response = _get(f"/outfits/{outfit_id}/images")
    response.raise_for_status()
    return response.json()


def upload_avatar(user_id: int, image: FileLike) -> dict:
    """Upload and store an avatar image for a user; return the avatar record."""
    files = {"file": (image.name, image.getvalue(), image.type)}
    response = _post(f"/users/{user_id}/avatar/", files=files)
    response.raise_for_status()
    return response.json()


def fetch_avatar(user_id: int) -> bytes | None:
    """Fetch a user's most recently uploaded avatar image, if any."""
    response = _get(f"/users/{user_id}/avatar/")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.content


def fetch_user(user_id: int) -> dict:
    """Fetch a user record, including the current ``credits`` balance."""
    response = _get(f"/users/{user_id}")
    response.raise_for_status()
    return response.json()
