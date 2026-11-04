"""HTTP client for the Closet Muse backend.

The frontend talks to the backend exclusively through this module — it must
never import ``closet_muse.db`` or ``closet_muse.services``.
"""

from io import BytesIO
from typing import Protocol

import requests
from PIL import Image

from closet_muse.domain.enums import WomenClothingMainCategory
from closet_muse.domain.schemas import ClothingBase
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


def polish_clothing_image(
    images: list[FileLike], garment_type: str, mannequin_form: str
) -> requests.Response:
    files = [("files", (image.name, image.getvalue(), image.type)) for image in images]
    data = {"garment_type": garment_type, "mannequin_form": mannequin_form}
    return _post("/images/polish/", files=files, data=data)


def generate_clothing_attributes(images: list[FileLike]) -> ClothingBase | None:
    files = [("files", (image.name, image.getvalue(), image.type)) for image in images]
    try:
        response = _post("/images/attributes/", files=files)
        response.raise_for_status()
        return ClothingBase(**response.json())
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI
        print(exc)
        return None


def upload_image(bucket: str, file: FileLike) -> str:
    files = {"file": (file.name, file.getvalue(), file.type)}
    response = _post(f"/images/upload/{bucket}/", files=files)
    response.raise_for_status()
    return response.json()["image_path"]


def fetch_image(bucket: str, filename: str) -> bytes:
    response = _get(f"/images/{bucket}/{filename}")
    response.raise_for_status()
    return response.content


def add_clothing_item(user_id: int, clothing: ClothingBase, image: FileLike) -> dict:
    # Upload first, then attach the returned filename to the record.
    filename = upload_image(settings.storage_bucket_clothing, image)
    payload = clothing.model_dump(mode="json")
    payload["image_path"] = filename

    response = _post(f"/clothing/{user_id}", json=payload)
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


def generate_outfit(user_id: int, clothing_ids: list[str]) -> Image.Image | None:
    """Generate an outfit image for a specific user based on the provided clothing IDs."""
    response = _post(
        f"/outfits/generate/{user_id}",
        json={"clothing_ids": clothing_ids},
    )
    if response.status_code != 200 or not response.content:
        return None
    return Image.open(BytesIO(response.content))


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
