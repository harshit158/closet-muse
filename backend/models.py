from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
from pydantic import BaseModel, Field

from datetime import datetime
from typing import Optional, List
from uuid import uuid4
from sqlmodel import SQLModel, Field, Relationship

from backend import types

class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    dob: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)

    body_profile: Optional["BodyProfile"] = Relationship(back_populates="user")
    clothes: List["ClothingItem"] = Relationship(back_populates="user")
    outfits: List["Outfit"] = Relationship(back_populates="user")
    generated_images: List["GeneratedImage"] = Relationship(back_populates="user")
    avatar_images: List["AvatarImage"] = Relationship(back_populates="user")


class BodyProfile(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    skin_tone: Optional[str] = None  # e.g., "fair", "medium", "olive", "dark"
    body_shape: Optional[str] = None  # e.g., "pear", "hourglass"
    avatar_image_path: Optional[str] = None  # Path to generated avatar image

    user: User = Relationship(back_populates="body_profile")
    
class AvatarImage(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    image_path: str

    user: User = Relationship(back_populates="avatar_images")

class OutfitClothingLink(SQLModel, table=True):
    outfit_id: int = Field(foreign_key="outfit.id", primary_key=True)
    clothing_item_id: str = Field(foreign_key="clothingitem.id", primary_key=True)
    
class ClothingItem(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: int = Field(foreign_key="user.id")

    # Hierarchical categories
    main_category: types.WomenClothingMainCategory
    sub_category: Optional[str] = None  # You’ll derive from Enum dynamically in app logic

    color: Optional[str] = None
    material: Optional[str] = None
    pattern: Optional[str] = None  # e.g., “floral”, “solid”, “striped”
    brand: Optional[str] = None
    size: Optional[str] = None
    season: Optional[types.Season] = None  # e.g., “summer”, “winter”
    image_path: Optional[str] = None  # Local path or cloud URL

    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="clothes")
    outfits: List["Outfit"] = Relationship(back_populates="clothing_items",link_model=OutfitClothingLink)


class Outfit(SQLModel, table=True):
    """Combination of multiple clothing items (user-created or AI-generated)."""
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    name: Optional[str] = None
    description: Optional[str] = None
    created_by_ai: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    rating: Optional[int] = None  # 1–5 stars
    occasion: Optional[types.Occasion] = None  # e.g., “office”, “party”, “casual”
    season: Optional[types.Season] = None

    user: User = Relationship(back_populates="outfits")
    generated_images: List["GeneratedImage"] = Relationship(back_populates="outfit")
    clothing_items: List["ClothingItem"] = Relationship(back_populates="outfits",link_model=OutfitClothingLink)

class GeneratedImage(SQLModel, table=True):
    """AI-generated visuals (for try-ons or AI outfits)."""
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    outfit_id: Optional[int] = Field(foreign_key="outfit.id")

    # Prompt & generation metadata
    prompt: str
    image_path: str  # Local file path or cloud URL

    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="generated_images")
    outfit: Optional[Outfit] = Relationship(back_populates="generated_images")


class SurpriseOutfit(SQLModel, table=True):
    """Stores surprise outfit generation history (AI styling suggestions)."""
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    outfit_id: int = Field(foreign_key="outfit.id")

    surprise_prompt: str  # e.g., "Mix casual and formal styles for a chic office look"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    feedback: Optional[str] = None  # User reaction or comments

    # No relationship back needed here unless you want reverse querying
