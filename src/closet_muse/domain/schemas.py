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
    dob: datetime.date


class ClothingBase(SQLModel):
    main_category: enums.WomenClothingMainCategory
    sub_category: Optional[str] = None

    # Dominant visible color (either standard or hex-mapped), e.g. "Beige", "#D0B987"
    color: Optional[str] = Field(
        default=None,
        description="Primary visible color of the item (standard name)",
    )

    # The same color as a hex code, for palette rendering, e.g. "#D0B987"
    color_hex: Optional[str] = Field(
        default=None,
        description="Primary visible color of the item as a hex code",
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

    # How the garment sits on the body, e.g. "Slim", "Oversized", "Relaxed"
    fit: Optional[str] = Field(
        default=None,
        description="How the garment sits on the body (slim, relaxed, oversized, ...)",
    )

    # Provenance: the mannequin form this item was polished onto. Lets the item
    # be re-polished or debugged later, since the form is not otherwise recorded.
    mannequin_form: Optional[str] = Field(
        default=None,
        description="Mannequin form the item's polished images were generated on",
    )

    image_path: Optional[str] = None

    # Second perspective of the same item: the garment dressed on the
    # three-quarter (tilted) mannequin. The try-on generator uses both images so
    # the model can read the garment's fit and drape from two angles. Items
    # onboarded before this existed have no tilted image.
    image_path_tilted: Optional[str] = None


class ClothingUpdate(SQLModel):
    """Partial update for a wardrobe item.

    Every field is optional so a PATCH only touches what the client sends
    (``model_dump(exclude_unset=True)``). ``image_path`` is intentionally
    absent: replacing an item's image is not supported here.
    """

    main_category: Optional[enums.WomenClothingMainCategory] = None
    sub_category: Optional[str] = None
    color: Optional[str] = None
    color_hex: Optional[str] = None
    material: Optional[enums.Material] = None
    pattern: Optional[enums.Pattern] = None
    brand: Optional[str] = None
    size: Optional[str] = None
    season: Optional[enums.Season] = None
    description: Optional[str] = None
    fit: Optional[str] = None
    mannequin_form: Optional[str] = None


class ClothingWithImage(BaseModel):
    clothing: ClothingBase
    image_data: bytes | None = None
    # The same garment on the three-quarter mannequin; ``None`` for items
    # onboarded before tilted images existed.
    image_data_tilted: bytes | None = None


class OutfitRequest(BaseModel):
    """Request to generate an outfit image from a set of wardrobe items."""

    clothing_ids: list[uuid.UUID]
