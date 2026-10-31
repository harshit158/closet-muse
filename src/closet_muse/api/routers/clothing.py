"""Clothing routes: list, count, and create wardrobe items."""

import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from closet_muse.api.deps import SessionDep
from closet_muse.db import models
from closet_muse.domain.enums import WomenClothingMainCategory
from closet_muse.domain.schemas import ClothingBase

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
