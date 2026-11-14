"""SQLModel table definitions.

Domain-only shapes (enums, DTOs, request models) live in
``closet_muse.domain``. ``ClothingBase`` and ``UserCreate`` are re-exported
here for convenience.
"""

import datetime
import uuid
from typing import Optional

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

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

    # The polished mannequin renders and the user's original uploads. Both are
    # eagerly loaded (``selectin``) because every read path needs them, and both
    # cascade so deleting an item never leaves orphaned child rows behind.
    images: list["ClothingImage"] = Relationship(
        back_populates="clothing",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )
    source_images: list["ClothingSourceImage"] = Relationship(
        back_populates="clothing",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )

    __table_args__ = (
        Index("ix_clothing_user_id", "user_id"),
        Index("ix_clothing_user_id_main_category", "user_id", "main_category"),
    )


class ClothingImage(SQLModel, table=True):
    """A polished render of one garment on one mannequin view.

    Replaces the old ``clothing.image_path`` / ``image_path_tilted`` columns: one row
    per view, so a third view needs no schema change. ``view`` is free text mirroring
    ``image_generation.MANNEQUIN_VIEWS`` (``"front"`` / ``"tilted"``), for the same
    reason ``OutfitImage.view`` is — the set of views is developer-curated config, not
    user data.

    ``__tablename__`` is set explicitly: SQLModel would otherwise derive
    ``clothingimage`` from the class name, and the plan (and revision ``0006``) name the
    table ``clothing_image``.
    """

    __tablename__ = "clothing_image"

    __table_args__ = (
        UniqueConstraint("clothing_id", "view", name="uq_clothingimage_clothing_view"),
        Index("ix_clothingimage_clothing_id", "clothing_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clothing_id: uuid.UUID = Field(foreign_key="clothing.id", ondelete="CASCADE")
    view: str
    image_path: str
    created_at: datetime.datetime = Field(default_factory=_utcnow)

    clothing: Optional["Clothing"] = Relationship(back_populates="images")


class ClothingSourceImage(SQLModel, table=True):
    """One of the user's original upload photos for a garment.

    These used to be read into memory, sent to the image model, and dropped — so the
    only copy of the user's photo was lost. Keeping them makes an item re-polishable
    with a different mannequin form. ``position`` preserves the upload order, with
    ``0`` as the primary reference.
    """

    __tablename__ = "clothing_source_image"

    __table_args__ = (Index("ix_clothingsourceimage_clothing_id", "clothing_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clothing_id: uuid.UUID = Field(foreign_key="clothing.id", ondelete="CASCADE")
    image_path: str
    position: int = 0
    created_at: datetime.datetime = Field(default_factory=_utcnow)

    clothing: Optional["Clothing"] = Relationship(back_populates="source_images")


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
    # User reaction to a generated outfit. Absorbed from the dropped
    # ``surpriseoutfit`` table, which never had a single row.
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


__all__ = [
    "User",
    "UserCreate",
    "AvatarImage",
    "Clothing",
    "ClothingBase",
    "ClothingImage",
    "ClothingSourceImage",
    "Outfit",
    "OutfitClothingLink",
    "OutfitImage",
]
