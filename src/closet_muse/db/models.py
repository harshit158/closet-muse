"""SQLModel table definitions.

Domain-only shapes (enums, DTOs, request models) live in
``closet_muse.domain``. ``ClothingBase`` and ``UserCreate`` are re-exported
here for convenience.
"""

import datetime
import uuid
from typing import Optional

from sqlmodel import Field, SQLModel

from closet_muse.domain.schemas import ClothingBase, UserCreate


class User(UserCreate, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class BodyProfile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    skin_tone: Optional[str] = None
    body_shape: Optional[str] = None
    avatar_image_path: Optional[str] = None


class AvatarImage(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    image_path: str


class Clothing(ClothingBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class OutfitClothingLink(SQLModel, table=True):
    outfit_id: uuid.UUID = Field(foreign_key="outfit.id", primary_key=True)
    clothing_item_id: uuid.UUID = Field(foreign_key="clothing.id", primary_key=True)


class Outfit(SQLModel, table=True):
    """Combination of multiple clothing items (user-created or AI-generated)."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    name: Optional[str] = None
    description: Optional[str] = None
    created_by_ai: bool = False
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    occasion: Optional[str] = None
    season: Optional[str] = None


class GeneratedImage(SQLModel, table=True):
    """AI-generated visuals (for try-ons or AI outfits)."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    outfit_id: Optional[uuid.UUID] = Field(default=None, foreign_key="outfit.id")

    # Prompt & generation metadata
    prompt: str
    image_path: str

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class SurpriseOutfit(SQLModel, table=True):
    """Stores surprise outfit generation history (AI styling suggestions)."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    outfit_id: uuid.UUID = Field(foreign_key="outfit.id")

    surprise_prompt: str
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    feedback: Optional[str] = None


__all__ = [
    "User",
    "UserCreate",
    "BodyProfile",
    "AvatarImage",
    "Clothing",
    "ClothingBase",
    "Outfit",
    "OutfitClothingLink",
    "GeneratedImage",
    "SurpriseOutfit",
]
