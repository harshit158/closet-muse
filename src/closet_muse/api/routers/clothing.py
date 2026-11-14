"""Clothing routes: list, count, create, update, and delete wardrobe items."""

import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from closet_muse.api.deps import SessionDep
from closet_muse.db import models
from closet_muse.domain.enums import WomenClothingMainCategory
from closet_muse.domain.schemas import (
    ClothingCreate,
    ClothingImageRead,
    ClothingRead,
    ClothingSourceImageRead,
    ClothingUpdate,
)
from closet_muse.services import storage
from closet_muse.settings import settings

router = APIRouter(prefix="/clothing", tags=["clothing"])


def _get_item_or_404(clothing_id: uuid.UUID, session: SessionDep) -> models.Clothing:
    item = session.get(models.Clothing, clothing_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Clothing item not found.")
    return item


@router.get("/counts/{user_id}")
def clothing_counts(user_id: int, session: SessionDep) -> dict[str, int]:
    """Return the number of items per main category for a user."""
    rows = session.exec(
        select(models.Clothing.main_category, func.count())
        .where(models.Clothing.user_id == user_id)
        .group_by(models.Clothing.main_category)
    ).all()
    return {category.name: count for category, count in rows}


@router.get("/{user_id}")
def list_clothing(
    user_id: int,
    session: SessionDep,
    main_category: WomenClothingMainCategory | None = None,
) -> list[ClothingRead]:
    """List a user's clothing items, optionally filtered by main category."""
    statement = select(models.Clothing).where(models.Clothing.user_id == user_id)
    if main_category is not None:
        statement = statement.where(models.Clothing.main_category == main_category)
    return [ClothingRead.model_validate(item) for item in session.exec(statement).all()]


@router.post("/{user_id}")
def add_clothing_item(
    user_id: int, clothing: ClothingCreate, session: SessionDep
) -> ClothingRead:
    """Add a clothing item to a user's wardrobe, with its polished views and uploads.

    The item, its ``clothing_image`` rows, and its ``clothing_source_image`` rows are
    written in one transaction, so a failure never leaves a garment without its images.
    """
    attributes = clothing.model_dump(exclude={"images", "source_image_paths"})
    db_clothing = models.Clothing(**attributes, user_id=user_id)
    session.add(db_clothing)
    # Assigns db_clothing.id so the children below can reference it.
    session.flush()

    for image in clothing.images:
        session.add(
            models.ClothingImage(
                clothing_id=db_clothing.id,
                view=image.view,
                image_path=image.image_path,
            )
        )
    for position, image_path in enumerate(clothing.source_image_paths):
        session.add(
            models.ClothingSourceImage(
                clothing_id=db_clothing.id,
                image_path=image_path,
                position=position,
            )
        )

    session.commit()
    session.refresh(db_clothing)
    return ClothingRead.model_validate(db_clothing)


@router.get("/item/{clothing_id}")
def get_clothing_item(clothing_id: uuid.UUID, session: SessionDep) -> ClothingRead:
    return ClothingRead.model_validate(_get_item_or_404(clothing_id, session))


@router.get("/item/{clothing_id}/images")
def list_clothing_images(
    clothing_id: uuid.UUID, session: SessionDep
) -> list[ClothingImageRead]:
    """Return the polished renders for one garment (one row per mannequin view)."""
    item = _get_item_or_404(clothing_id, session)
    return [ClothingImageRead.model_validate(image) for image in item.images]


@router.get("/item/{clothing_id}/source-images")
def list_clothing_source_images(
    clothing_id: uuid.UUID, session: SessionDep
) -> list[ClothingSourceImageRead]:
    """Return the user's original upload photos for one garment, in upload order."""
    item = _get_item_or_404(clothing_id, session)
    return [
        ClothingSourceImageRead.model_validate(image)
        for image in sorted(item.source_images, key=lambda image: image.position)
    ]


@router.patch("/item/{clothing_id}")
def update_clothing_item(
    clothing_id: uuid.UUID, clothing: ClothingUpdate, session: SessionDep
) -> ClothingRead:
    """Update the provided fields of a wardrobe item (partial update)."""
    item = _get_item_or_404(clothing_id, session)

    for field, value in clothing.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    session.add(item)
    session.commit()
    session.refresh(item)
    return ClothingRead.model_validate(item)


@router.delete("/item/{clothing_id}")
def delete_clothing_item(
    clothing_id: uuid.UUID, session: SessionDep
) -> dict[str, str]:
    """Delete a wardrobe item, its stored images, and any outfit links."""
    item = _get_item_or_404(clothing_id, session)

    # SQLite foreign keys are enforced at runtime (``db/engine.py``), so the child rows
    # would go with the item anyway. They are collected first regardless, because their
    # filenames are needed to delete the files — and a file left behind is unrecoverable
    # dead weight, whereas a redundant DELETE costs one indexed query.
    links = session.exec(
        select(models.OutfitClothingLink).where(
            models.OutfitClothingLink.clothing_item_id == clothing_id
        )
    ).all()
    for link in links:
        session.delete(link)

    # Best-effort file cleanup; a missing file is not an error.
    for image in item.images:
        storage.delete_image(settings.storage_bucket_clothing, image.image_path)
    for source in item.source_images:
        storage.delete_image(settings.storage_bucket_clothing_source, source.image_path)

    session.delete(item)
    session.commit()
    return {"status": "deleted", "id": str(clothing_id)}
