from enum import Enum


class TopCategory(Enum):
    TSHIRT = "T-Shirt"
    SHIRT_BLOUSE = "Shirt / Blouse"
    TANK_CAMI = "Tank Top / Camisole"
    SWEATER = "Sweater"
    SWEATSHIRT_HOODIE = "Sweatshirt / Hoodie"
    CROP_TOP = "Crop Top"
    BRALETTE_TUBE = "Bralette / Tube Top"


class BottomCategory(Enum):
    JEANS = "Jeans"
    TROUSERS_PANTS = "Trousers / Pants"
    LEGGINGS = "Leggings"
    SHORTS = "Shorts"
    SKIRTS = "Skirts"


class OnePieceCategory(Enum):
    DRESS = "Dress"
    JUMPSUIT = "Jumpsuit"
    ROMPER = "Romper / Playsuit"


class OuterwearCategory(Enum):
    JACKET = "Jacket"
    COAT = "Coat"
    BLAZER = "Blazer"
    SHRUG_CAPE = "Shrug / Cape"
    VEST = "Vest"


class LoungewearCategory(Enum):
    SLEEPWEAR = "Sleepwear"
    LOUNGEWEAR = "Loungewear"
    ROBE = "Robe"


class AccessoryCategory(Enum):
    NECKWEAR = "Scarf / Shawl"
    WAISTWEAR = "Belt"
    HEADWEAR = "Hat / Cap"
    HANDWEAR = "Gloves"
    LEGWEAR = "Stockings / Tights"


class FootwearCategory(Enum):
    HEELS = "Heels"
    FLATS = "Flats"
    SNEAKERS = "Sneakers"
    BOOTS = "Boots"
    SANDALS = "Sandals"
    LOAFERS = "Loafers"
    OTHER = "Other"


class WomenClothingMainCategory(str, Enum):
    TOPS = "Tops"
    BOTTOMS = "Bottoms"
    ONE_PIECE = "One-Piece Outfits"
    FOOTWEAR = "Footwear"
    OUTERWEAR = "Outerwear"
    LOUNGEWEAR = "Loungewear"
    ACCESSORIES = "Accessories"


CATEGORY_MAPPING = {
    WomenClothingMainCategory.TOPS: TopCategory,
    WomenClothingMainCategory.BOTTOMS: BottomCategory,
    WomenClothingMainCategory.ONE_PIECE: OnePieceCategory,
    WomenClothingMainCategory.FOOTWEAR: FootwearCategory,
    WomenClothingMainCategory.OUTERWEAR: OuterwearCategory,
    WomenClothingMainCategory.LOUNGEWEAR: LoungewearCategory,
    WomenClothingMainCategory.ACCESSORIES: AccessoryCategory,
}


class Season(str, Enum):
    SPRING = "Spring"
    SUMMER = "Summer"
    FALL = "Fall"
    WINTER = "Winter"
    ALL_SEASONS = "All Seasons"


class Occasion(str, Enum):
    CASUAL = "Casual"
    PARTY = "Party"
    WORK = "Work"
    SPORTS = "Sports"
    BEACH = "Beach"
    SLEEPWEAR = "Sleepwear"


class Material(str, Enum):
    COTTON = "Cotton"
    DENIM = "Denim"
    POLYESTER = "Polyester"
    LINEN = "Linen"
    SILK = "Silk"
    WOOL = "Wool"
    LEATHER = "Leather"
    OTHER = "Other"


class Pattern(str, Enum):
    SOLID = "Solid"
    STRIPED = "Striped"
    CHECKERED = "Checkerboard"
    PLAIN = "Plain"
    POLKA_DOT = "Polka Dot"
    FLORAL = "Floral"
    GEOMETRIC = "Geometric"
    PRINT = "Print"
    OTHER = "Other"
