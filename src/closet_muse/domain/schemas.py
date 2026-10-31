"""Transport DTOs shared between the backend and the frontend.

These are plain (non-table) models: they describe the wire/domain shape and
never touch the database or services.
"""

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel
from sqlmodel import SQLModel, Field

from closet_muse.domain import enums


class UserCreate(SQLModel):
    name: str
    dob: datetime.datetime


class ClothingBase(SQLModel):
    main_category: enums.WomenClothingMainCategory
    sub_category: Optional[str] = None

    # Dominant visible color (either standard or hex-mapped), e.g. "Beige", "#D0B987"
    color: Optional[str] = Field(
        default=None,
        description="Primary visible color of the item (standard name)",
    )

    # Key fabric or production material, e.g. "Cotton", "Silk Blend", "Denim"
    material: Optional[enums.Material] = Field(
        default=None,
        description="Main fabric or material composition of the item",
    )

    # Visual or print style, e.g. "Solid", "Floral", "Striped", "Animal Print"
    pattern: Optional[enums.Pattern] = Field(
        default=None,
        description="Visual design or print style displayed on the item",
    )

    # Manufacturer or label name, e.g. "Zara", "Uniqlo", "H&M"
    brand: Optional[str] = None

    # Sizing label according to seller standard, e.g. "S", "M", "L", "28", "Free Size"
    size: Optional[str] = None

    # Best-suited season for use, e.g. "Summer", "Winter", "All-season"
    season: Optional[enums.Season] = Field(
        default=None,
        description="Seasonal suitability based on fabric, design, and intended use",
    )

    description: Optional[str] = Field(
        default=None,
        description=(
            "Image description in detail, focusing on the dress including its "
            "color, pattern, fabric, style, fit, etc."
        ),
    )

    image_path: Optional[str] = None


class ClothingWithImage(BaseModel):
    clothing: ClothingBase
    image_data: bytes | None = None


class OutfitRequest(BaseModel):
    """Request to generate an outfit image from a set of wardrobe items."""

    clothing_ids: list[uuid.UUID]
