"""Clothing routes: list, count, create, update, and delete wardrobe items."""

import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from closet_muse.api.deps import SessionDep
from closet_muse.db import models
from closet_muse.domain.enums import WomenClothingMainCategory
from closet_muse.domain.schemas import ClothingBase, ClothingUpdate
from closet_muse.services import storage
from closet_muse.settings import settings

router = APIRouter(prefix="/clothing", tags=["clothing"])


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
) -> list[models.Clothing]:
    """List a user's clothing items, optionally filtered by main category."""
    statement = select(models.Clothing).where(models.Clothing.user_id == user_id)
    if main_category is not None:
        statement = statement.where(models.Clothing.main_category == main_category)
    return list(session.exec(statement).all())


@router.post("/{user_id}")
def add_clothing_item(
    user_id: int, clothing: ClothingBase, session: SessionDep
) -> models.Clothing:
    """Add a clothing item to a user's wardrobe."""
    db_clothing = models.Clothing(**clothing.model_dump(), user_id=user_id)
    session.add(db_clothing)
    session.commit()
    session.refresh(db_clothing)
    return db_clothing


@router.get("/item/{clothing_id}")
def get_clothing_item(clothing_id: uuid.UUID, session: SessionDep) -> models.Clothing:
    item = session.get(models.Clothing, clothing_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Clothing item not found.")
    return item


@router.patch("/item/{clothing_id}")
def update_clothing_item(
    clothing_id: uuid.UUID, clothing: ClothingUpdate, session: SessionDep
) -> models.Clothing:
    """Update the provided fields of a wardrobe item (partial update)."""
    item = session.get(models.Clothing, clothing_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Clothing item not found.")

    for field, value in clothing.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/item/{clothing_id}")
def delete_clothing_item(
    clothing_id: uuid.UUID, session: SessionDep
) -> dict[str, str]:
    """Delete a wardrobe item, its stored image, and any outfit links."""
    item = session.get(models.Clothing, clothing_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Clothing item not found.")

    # SQLite foreign keys are not enforced, so remove outfit links explicitly
    # rather than leaving orphaned rows behind.
    links = session.exec(
        select(models.OutfitClothingLink).where(
            models.OutfitClothingLink.clothing_item_id == clothing_id
        )
    ).all()
    for link in links:
        session.delete(link)

    # Best-effort image cleanup; a missing file is not an error.
    if item.image_path:
        storage.delete_image(settings.storage_bucket_clothing, item.image_path)

    session.delete(item)
    session.commit()
    return {"status": "deleted", "id": str(clothing_id)}
