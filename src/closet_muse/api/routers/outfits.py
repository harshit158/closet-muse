"""Outfit routes: virtual try-on generation from wardrobe items."""

import io
import uuid
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from closet_muse.api.deps import SessionDep
from closet_muse.db import models
from closet_muse.domain.schemas import ClothingBase, ClothingWithImage, OutfitRequest
from closet_muse.services import image_generation, storage
from closet_muse.settings import settings

router = APIRouter(prefix="/outfits", tags=["outfits"])


@router.post("/generate/{user_id}")
def generate_outfit(
    user_id: int, request: OutfitRequest, session: SessionDep
) -> Response:
    """Generate a virtual try-on image per model view from selected wardrobe items.

    Every view in ``settings.model_image_views`` is dressed in the same outfit, so
    the response is a ZIP archive holding one PNG per view (``left.png``,
    ``center.png``, ``right.png``).
    """
    selections: dict[str, ClothingWithImage] = {}

    for clothing_id in request.clothing_ids:
        item = session.get(models.Clothing, clothing_id)
        if item is None or item.user_id != user_id:
            raise HTTPException(
                status_code=404, detail=f"Clothing item {clothing_id} not found."
            )

        data = storage.read_image(
            settings.storage_bucket_clothing, item.image_path or ""
        )
        # The tilted perspective is optional: items onboarded before it existed
        # have no second image, and the try-on prompt handles a single reference.
        tilted_data = (
            storage.read_image(
                settings.storage_bucket_clothing, item.image_path_tilted
            )
            if item.image_path_tilted
            else None
        )
        category = item.main_category
        key = category.value if hasattr(category, "value") else str(category)
        selections[key] = ClothingWithImage(
            clothing=ClothingBase(**item.model_dump()),
            image_data=data,
            image_data_tilted=tilted_data,
        )

    # One try-on per model view; fall back to the single subject image when no
    # view map is configured.
    model_paths = settings.model_image_views or {
        "center": settings.model_image_path
    }
    try:
        views = image_generation.generate_fashion_images(selections, model_paths)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for view, image_bytes in views.items():
            storage.save_image(settings.storage_bucket_generated, image_bytes)
            archive.writestr(f"{view}.png", image_bytes)
    return Response(content=buffer.getvalue(), media_type="application/zip")


@router.get("/image/{filename}")
def get_generated_image(filename: str) -> Response:
    try:
        data = storage.read_image(settings.storage_bucket_generated, filename)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Image not found.")
    return Response(content=data, media_type="image/png")


@router.get("/{outfit_id}")
def get_outfit(outfit_id: uuid.UUID, session: SessionDep) -> models.Outfit:
    outfit = session.get(models.Outfit, outfit_id)
    if outfit is None:
        raise HTTPException(status_code=404, detail="Outfit not found.")
    return outfit
