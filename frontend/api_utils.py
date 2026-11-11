"""HTTP client for the Closet Muse backend.

The frontend talks to the backend exclusively through this module — it must
never import ``closet_muse.db`` or ``closet_muse.services``.
"""

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


def _post(path: str, **kwargs) -> requests.Response:
    return requests.post(f"{settings.backend_url}{path}", timeout=TIMEOUT, **kwargs)


def _get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{settings.backend_url}{path}", timeout=TIMEOUT, **kwargs)


def _patch(path: str, **kwargs) -> requests.Response:
    return requests.patch(f"{settings.backend_url}{path}", timeout=TIMEOUT, **kwargs)


def _delete(path: str, **kwargs) -> requests.Response:
    return requests.delete(f"{settings.backend_url}{path}", timeout=TIMEOUT, **kwargs)


def polish_clothing_image(
    images: list[FileLike], garment_type: str, mannequin_form: str
) -> dict[str, bytes]:
    """Dress both mannequin perspectives in the garment.

    The backend returns a ZIP archive holding one PNG per view, so this unpacks
    it into ``{"front": bytes, "tilted": bytes}``. Raises ``requests.HTTPError``
    on a failed request and ``ValueError`` if the archive is missing a view.
    """
    files = [("files", (image.name, image.getvalue(), image.type)) for image in images]
    data = {"garment_type": garment_type, "mannequin_form": mannequin_form}
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
) -> ClothingBase:
    """Extract clothing attributes from the uploaded photos.

    ``main_category`` is the garment type the user already selected; when given,
    the backend constrains the category and sub-category to it, so the result
    always fits the form.

    Raises ``requests.HTTPError`` on a failed request so the caller can surface
    the failure; extraction is a user-triggered step of its own.
    """
    files = [("files", (image.name, image.getvalue(), image.type)) for image in images]
    data = {"main_category": main_category.value} if main_category else None
    response = _post("/images/attributes/", files=files, data=data)
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
) -> dict:
    """Create a wardrobe item, uploading its front and tilted images.

    ``image_tilted`` is the same garment on the three-quarter mannequin; it is
    optional so an item can still be saved with a single perspective.
    """
    # Upload first, then attach the returned filenames to the record.
    filename = upload_image(settings.storage_bucket_clothing, image)
    payload = clothing.model_dump(mode="json")
    payload["image_path"] = filename

    if image_tilted is not None:
        payload["image_path_tilted"] = upload_image(
            settings.storage_bucket_clothing, image_tilted
        )

    response = _post(f"/clothing/{user_id}", json=payload)
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


def generate_outfit(user_id: int, clothing_ids: list[str]) -> dict[str, bytes] | None:
    """Generate one outfit image per model view for the given clothing IDs.

    The backend returns a ZIP archive holding one PNG per model view, so this
    unpacks it into ``{"left": bytes, "center": bytes, "right": bytes}``.
    Returns ``None`` on a failed or empty response.
    """
    response = _post(
        f"/outfits/generate/{user_id}",
        json={"clothing_ids": clothing_ids},
    )
    if response.status_code != 200 or not response.content:
        return None

    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        return {
            name.removesuffix(".png"): archive.read(name)
            for name in archive.namelist()
            if name.endswith(".png")
        }


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
