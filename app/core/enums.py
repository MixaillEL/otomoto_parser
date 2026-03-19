"""Otomoto Parser – Core enums."""
from enum import Enum


class FuelType(str, Enum):
    PETROL = "petrol"
    DIESEL = "diesel"
    HYBRID = "hybrid"
    ELECTRIC = "electric"
    LPG = "lpg"
    CNG = "cng"

    # Otomoto API values (for URL building)
    @property
    def otomoto_value(self) -> str:
        _map = {
            "petrol": "petrol",
            "diesel": "diesel",
            "hybrid": "hybrid",
            "electric": "electric",
            "lpg": "lpg",
            "cng": "cng",
        }
        return _map[self.value]


class Transmission(str, Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"

    @property
    def otomoto_value(self) -> str:
        return {"manual": "manual", "automatic": "automatic"}[self.value]


class BodyType(str, Enum):
    SEDAN = "sedan"
    HATCHBACK = "compact"
    COMBI = "combi"
    SUV = "suv"
    COUPE = "coupe"
    CABRIOLET = "cabriolet"
    VAN = "van"
    MINIBUS = "minibus"
    PICKUP = "pickup"

    @property
    def otomoto_value(self) -> str:
        return self.value


class SortOrder(str, Enum):
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    LATEST = "latest"
    MILEAGE_ASC = "mileage_asc"

    @property
    def otomoto_value(self) -> str:
        _map = {
            "price_asc": "filter_float_price%3Aasc",
            "price_desc": "filter_float_price%3Adesc",
            "latest": "created_at%3Adesc",
            "mileage_asc": "filter_float_mileage%3Aasc",
        }
        return _map[self.value]


class SellerType(str, Enum):
    PRIVATE = "private"
    DEALER = "dealer"
    UNKNOWN = "unknown"
