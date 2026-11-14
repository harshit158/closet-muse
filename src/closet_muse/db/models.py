"""SQLModel table definitions.

Domain-only shapes (enums, DTOs, request models) live in
``closet_muse.domain``. ``ClothingBase`` and ``UserCreate`` are re-exported
here for convenience.
"""

import datetime
import uuid
from typing import Optional

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from closet_muse.domain import enums
from closet_muse.domain.schemas import ClothingBase, UserCreate


def _utcnow() -> datetime.datetime:
    """Timezone-aware timestamp used by every ``created_at`` / ``updated_at``."""
    return datetime.datetime.now(datetime.timezone.utc)


class User(UserCreate, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime.datetime = Field(default_factory=_utcnow)
    updated_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column_kwargs={"onupdate": _utcnow},
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
    created_at: datetime.datetime = Field(default_factory=_utcnow)

    __table_args__ = (Index("ix_avatarimage_user_id", "user_id"),)


class Clothing(ClothingBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime.datetime = Field(default_factory=_utcnow)
    updated_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column_kwargs={"onupdate": _utcnow},
    )
    # Soft-delete flag. Added but not wired to any endpoint yet (out of scope).
    is_archived: bool = Field(default=False)

    __table_args__ = (
        Index("ix_clothing_user_id", "user_id"),
        Index("ix_clothing_user_id_main_category", "user_id", "main_category"),
    )


class OutfitClothingLink(SQLModel, table=True):
    """Which garments form an outfit. Rows go away with their outfit or garment."""

    outfit_id: uuid.UUID = Field(
        foreign_key="outfit.id", primary_key=True, ondelete="CASCADE"
    )
    clothing_item_id: uuid.UUID = Field(
        foreign_key="clothing.id", primary_key=True, ondelete="CASCADE"
    )

    # The composite PK covers (outfit_id, clothing_item_id), so the delete path —
    # which filters on clothing_item_id alone — would otherwise full-scan.
    __table_args__ = (
        Index("ix_outfitclothinglink_clothing_item_id", "clothing_item_id"),
    )


class Outfit(SQLModel, table=True):
    """Combination of multiple clothing items (user-created or AI-generated)."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    name: Optional[str] = None
    description: Optional[str] = None
    created_by_ai: bool = False
    created_at: datetime.datetime = Field(default_factory=_utcnow)
    updated_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column_kwargs={"onupdate": _utcnow},
    )
    occasion: Optional[enums.Occasion] = None
    season: Optional[enums.Season] = None
    # User reaction to a generated outfit; migrated here from the dropped
    # ``SurpriseOutfit`` table.
    feedback: Optional[str] = None

    __table_args__ = (Index("ix_outfit_user_id", "user_id"),)


class OutfitImage(SQLModel, table=True):
    """A persisted try-on render: one row per model view per outfit.

    Ordering is deliberately not stored. The frontend fetches every view for an outfit
    and orders them against ``settings.model_image_views``, so adding or renaming a view
    needs no schema change. ``view`` is therefore free text, not an enum.

    ``model`` is the only generation metadata kept: ``settings.image_model_tryon``
    changes over time, so the model that actually rendered a row cannot be re-derived
    later. The prompt is reconstructible from the linked clothing rows and is not stored.

    SQLModel derives the table name from the class name (``OutfitImage`` ->
    ``outfitimage``), so ``__tablename__`` is deliberately not set.
    """

    __table_args__ = (
        UniqueConstraint("outfit_id", "view", name="uq_outfitimage_outfit_view"),
        Index("ix_outfitimage_user_id", "user_id"),
        Index("ix_outfitimage_outfit_id", "outfit_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    # An outfit image with no outfit is a contradiction, so this is NOT NULL.
    outfit_id: uuid.UUID = Field(foreign_key="outfit.id")

    view: str
    image_path: str
    model: str

    created_at: datetime.datetime = Field(default_factory=_utcnow)


class SurpriseOutfit(SQLModel, table=True):
    """Stores surprise outfit generation history (AI styling suggestions)."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    outfit_id: uuid.UUID = Field(foreign_key="outfit.id")

    surprise_prompt: str
    created_at: datetime.datetime = Field(default_factory=_utcnow)
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
    "OutfitImage",
    "SurpriseOutfit",
]
