from pydantic import BaseModel, Field

import datetime
from typing import Optional, List
import uuid
from sqlmodel import SQLModel, Field, Relationship

from backend import types

class UserCreate(SQLModel):
    name: str
    dob: datetime.datetime

class User(UserCreate, table=True):
    __table_args__ = {"extend_existing": True}
    
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    # body_profile: Optional["BodyProfile"] = Relationship(back_populates="user")
    # clothes: List["Clothing"] = Relationship(back_populates="user")
    # outfits: List["Outfit"] = Relationship(back_populates="user")
    # generated_images: List["GeneratedImage"] = Relationship(back_populates="user")
    # avatar_images: List["AvatarImage"] = Relationship(back_populates="user")


class BodyProfile(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    skin_tone: Optional[str] = None
    body_shape: Optional[str] = None
    avatar_image_path: Optional[str] = None

    # user: User = Relationship(back_populates="body_profile") 
    
class AvatarImage(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    image_path: str

    # user: User = Relationship(back_populates="avatar_images")

class OutfitClothingLink(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    outfit_id: uuid.UUID = Field(foreign_key="outfit.id", primary_key=True)
    clothing_item_id: uuid.UUID = Field(foreign_key="clothing.id", primary_key=True) 

class ClothingBase(SQLModel):
    main_category: types.WomenClothingMainCategory
    sub_category: Optional[str] = None

    # Dominant visible color (either standard or hex-mapped), e.g. "Beige", "#D0B987"
    color: Optional[str] = Field(
        default=None,
        description="Primary visible color of the item (standard name)"
    )
    
    # Key fabric or production material, e.g. "Cotton", "Silk Blend", "Denim"
    material: Optional[types.Material] = Field(
        default=None,
        description="Main fabric or material composition of the item"
    )
    
    # Visual or print style, e.g. "Solid", "Floral", "Striped", "Animal Print"
    pattern: Optional[types.Pattern] = Field(
        default=None,
        description="Visual design or print style displayed on the item"
    )
    
    # Manufacturer or label name, e.g. "Zara", "Uniqlo", "H&M"
    brand: Optional[str] = None
    
    # Sizing label according to seller standard, e.g. “S”, “M”, “L”, “28”, “Free Size”
    size: Optional[str] = None
    
    # Best-suited season for use, e.g. "Summer", "Winter", "All-season"
    season: Optional[types.Season] = Field(
        default=None,
        description="Seasonal suitability based on fabric, design, and intended use"
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Image description in detail, focusing on the dress including its color, pattern, fabric, style, fit, etc."
    )
    
    image_path: Optional[str] = None

class Clothing(ClothingBase, table=True):
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    # Relationships
    # user: User = Relationship(back_populates="clothes")
    # outfits: List["Outfit"] = Relationship(back_populates="clothing_items",link_model=OutfitClothingLink)

class ClothingWithImage(BaseModel):
    clothing: ClothingBase
    image_data: bytes | None = None

class Outfit(SQLModel, table=True):
    """Combination of multiple clothing items (user-created or AI-generated)."""
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    name: Optional[str] = None
    description: Optional[str] = None
    created_by_ai: bool = False
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    occasion: Optional[types.Occasion] = None
    season: Optional[types.Season] = None

    # Relationships
    # user: User = Relationship(back_populates="outfits")
    # generated_images: List["GeneratedImage"] = Relationship(back_populates="outfit")
    # clothing_items: List["Clothing"] = Relationship(back_populates="outfits",link_model=OutfitClothingLink)

class GeneratedImage(SQLModel, table=True):
    """AI-generated visuals (for try-ons or AI outfits)."""
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    outfit_id: Optional[uuid.UUID] = Field(foreign_key="outfit.id")

    # Prompt & generation metadata
    prompt: str
    image_path: str

    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    # Relationships
    # user: User = Relationship(back_populates="generated_images")
    # outfit: Optional[Outfit] = Relationship(back_populates="generated_images") 


class SurpriseOutfit(SQLModel, table=True):
    """Stores surprise outfit generation history (AI styling suggestions)."""
    __table_args__ = {"extend_existing": True}
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    outfit_id: uuid.UUID = Field(foreign_key="outfit.id")

    surprise_prompt: str
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    feedback: Optional[str] = None