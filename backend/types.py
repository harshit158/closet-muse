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

class IntimateLoungewearCategory(Enum):
    BRA = "Bra"
    PANTY = "Panty"
    SLEEPWEAR = "Sleepwear"
    LOUNGEWEAR = "Loungewear"
    ROBE = "Robe"

class ActivewearCategory(Enum):
    TOP = "Active Top"
    BOTTOM = "Active Bottom"
    SET = "Active Set"
    OUTERWEAR = "Active Outerwear"

class EthnicWearCategory(Enum):
    INDIAN = "Indian Wear"
    MIDDLE_EASTERN = "Middle Eastern Wear"
    FUSION = "Fusion Wear"

class SwimwearCategory(Enum):
    SWIMWEAR = "Swimwear"
    COVERUP = "Cover-up"

class AccessoryCategory(Enum):
    NECKWEAR = "Scarf / Shawl"
    WAISTWEAR = "Belt"
    HEADWEAR = "Hat / Cap"
    HANDWEAR = "Gloves"
    LEGWEAR = "Stockings / Tights"

class WomenClothingMainCategory(Enum):
    TOPS = "Tops"
    BOTTOMS = "Bottoms"
    ONE_PIECE = "One-Piece Outfits"
    OUTERWEAR = "Outerwear"
    INTIMATES_LOUNGE = "Intimates & Loungewear"
    ACTIVEWEAR = "Activewear"
    ETHNIC = "Ethnic / Cultural Wear"
    SWIMWEAR = "Swimwear & Beachwear"
    ACCESSORIES = "Accessories"
    
class Season(Enum):
    SPRING = "Spring"
    SUMMER = "Summer"
    FALL = "Fall"
    WINTER = "Winter"
    ALL_SEASONS = "All Seasons"

class Occasion(Enum):
    CASUAL = "Casual"
    PARTY = "Party"
    WORK = "Work"
    SPORTS = "Sports"
    BEACH = "Beach"
    SLEEPWEAR = "Sleepwear"