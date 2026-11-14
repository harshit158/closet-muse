"""Outfit routes: virtual try-on generation and saved-outfit history."""

import io
import uuid
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlmodel import Session, select

from closet_muse.api.deps import SessionDep
from closet_muse.db import models
from closet_muse.domain.schemas import ClothingBase, ClothingWithImage, OutfitRequest
from closet_muse.services import image_generation, storage
from closet_muse.settings import settings

router = APIRouter(prefix="/outfits", tags=["outfits"])


def _load_selections(
    user_id: int, clothing_ids: list[uuid.UUID], session: Session
) -> tuple[dict[str, ClothingWithImage], list[models.Clothing]]:
    """Resolve the requested items into try-on references.

    Returns the prompt payload (keyed by main category, as the generator expects) and
    the rows themselves, which the caller links to the new outfit.
    """
    selections: dict[str, ClothingWithImage] = {}
    items: list[models.Clothing] = []

    for clothing_id in clothing_ids:
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
        items.append(item)

    return selections, items


def _persist_outfit(
    user_id: int,
    items: list[models.Clothing],
    views: dict[str, bytes],
    session: Session,
) -> models.Outfit:
    """Write the outfit, its garment links, and one image row per view.

    The whole write is one transaction: if any step fails, the rows are rolled back
    and the files already written are removed, so a failed generation never leaves a
    half-written outfit (or orphaned PNGs) behind.
    """
    outfit = models.Outfit(user_id=user_id, created_by_ai=True)
    session.add(outfit)
    # Assigns outfit.id so the children below can reference it.
    session.flush()

    for item in items:
        session.add(
            models.OutfitClothingLink(outfit_id=outfit.id, clothing_item_id=item.id)
        )

    saved: list[str] = []
    try:
        for view, image_bytes in views.items():
            filename = storage.save_image(
                settings.storage_bucket_generated, image_bytes
            )
            saved.append(filename)
            session.add(
                models.OutfitImage(
                    user_id=user_id,
                    outfit_id=outfit.id,
                    view=view,
                    image_path=filename,
                    # The model that rendered this row cannot be re-derived later,
                    # because settings.image_model_tryon changes over time.
                    model=settings.image_model_tryon,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        for filename in saved:
            storage.delete_image(settings.storage_bucket_generated, filename)
        raise

    session.refresh(outfit)
    return outfit


@router.post("/generate/{user_id}")
def generate_outfit(
    user_id: int, request: OutfitRequest, session: SessionDep
) -> Response:
    """Generate a virtual try-on image per model view from selected wardrobe items.

    Every view in ``settings.model_image_views`` is dressed in the same outfit, so
    the response is a ZIP archive holding one PNG per view (``left.png``,
    ``center.png``, ``right.png``).

    The outfit is persisted before the response is built: one ``outfit`` row, one
    ``outfitclothinglink`` row per garment, and one ``outfitimage`` row per view. Its
    id is returned in the ``X-Outfit-Id`` header, since the body is a binary ZIP.
    """
    selections, items = _load_selections(user_id, request.clothing_ids, session)

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

    outfit = _persist_outfit(user_id, items, views, session)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for view, image_bytes in views.items():
            archive.writestr(f"{view}.png", image_bytes)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"X-Outfit-Id": str(outfit.id)},
    )


@router.get("/image/{filename}")
def get_generated_image(filename: str) -> Response:
    try:
        data = storage.read_image(settings.storage_bucket_generated, filename)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Image not found.")
    return Response(content=data, media_type="image/png")


@router.get("/{user_id}/history")
def list_outfit_history(user_id: int, session: SessionDep) -> list[models.Outfit]:
    """List a user's saved outfits, newest first."""
    statement = (
        select(models.Outfit)
        .where(models.Outfit.user_id == user_id)
        .order_by(models.Outfit.created_at.desc())
    )
    return list(session.exec(statement).all())


@router.get("/{outfit_id}/images")
def list_outfit_images(
    outfit_id: uuid.UUID, session: SessionDep
) -> list[models.OutfitImage]:
    """Return the persisted renders for one outfit.

    Rows come back in no guaranteed order: the frontend orders them against
    ``settings.model_image_views``, which is why no ordering column is stored.
    """
    if session.get(models.Outfit, outfit_id) is None:
        raise HTTPException(status_code=404, detail="Outfit not found.")

    statement = select(models.OutfitImage).where(
        models.OutfitImage.outfit_id == outfit_id
    )
    return list(session.exec(statement).all())


@router.get("/{outfit_id}")
def get_outfit(outfit_id: uuid.UUID, session: SessionDep) -> models.Outfit:
    outfit = session.get(models.Outfit, outfit_id)
    if outfit is None:
        raise HTTPException(status_code=404, detail="Outfit not found.")
    return outfit
