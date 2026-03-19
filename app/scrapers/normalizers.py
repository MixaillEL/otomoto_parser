"""Otomoto Parser – Raw data normalizers.

Converts raw string dicts (from parsers) into typed domain values.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.core.enums import BodyType, FuelType, SellerType, Transmission
from app.core.utils import (
    clean,
    extract_otomoto_id,
    normalize_listing_url,
    parse_engine_cc,
    parse_mileage,
    parse_power_hp,
    parse_price,
    parse_year,
)

logger = logging.getLogger(__name__)


@dataclass
class ListingData:
    """Typed, cleaned listing ready for storage."""

    # Identity
    otomoto_id: str = ""
    url: str = ""
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Core fields
    title: str = ""
    price_pln: Optional[int] = None
    year: Optional[int] = None
    mileage_km: Optional[int] = None

    # Engine / drivetrain
    fuel_type: str = ""
    transmission: str = ""
    engine_cc: Optional[int] = None
    power_hp: Optional[int] = None

    # Body
    body_type: str = ""
    colour: str = ""
    condition: str = ""

    # Seller
    seller_type: str = ""
    location: str = ""

    # Content
    description: str = ""
    thumbnail_url: str = ""
    origin_country: str = ""
    published_at: Optional[datetime] = None
    photos_json: str = ""
    source_category: str = ""
    raw_attributes_json: str = ""


def normalize_listing(raw: dict) -> ListingData:
    """Convert a raw merged dict (search card + detail) to a typed ListingData."""
    data = ListingData()

    data.url = normalize_listing_url(raw.get("url") or "")
    data.otomoto_id = clean(str(raw.get("id") or "")) or extract_otomoto_id(data.url)
    data.title = clean(raw.get("title") or "")
    data.description = clean(raw.get("description") or "")
    data.thumbnail_url = clean(raw.get("thumbnail_url") or "")
    data.source_category = clean(raw.get("source_category") or "")
    data.raw_attributes_json = _normalize_json_field(raw.get("raw_attributes_json"))
    data.photos_json = _normalize_json_field(raw.get("photos") or raw.get("photos_json"))
    data.published_at = _parse_datetime(raw.get("published_at"))

    # Price
    price_raw = raw.get("price_raw") or ""
    data.price_pln = parse_price(price_raw)

    # Year
    year_raw = raw.get("year_raw") or ""
    data.year = parse_year(year_raw)

    # Mileage
    mileage_raw = raw.get("mileage_raw") or ""
    data.mileage_km = parse_mileage(mileage_raw)

    # Engine
    data.engine_cc = parse_engine_cc(raw.get("engine_cc_raw") or "")
    data.power_hp = parse_power_hp(raw.get("power_hp_raw") or "")

    # Fuel type
    fuel_str = clean(raw.get("fuel_raw") or "").lower()
    data.fuel_type = _map_fuel(fuel_str)

    # Transmission
    trans_str = clean(raw.get("transmission_raw") or "").lower()
    data.transmission = _map_transmission(trans_str)

    # Body type
    body_str = clean(raw.get("body_type_raw") or "").lower()
    data.body_type = _map_body_type(body_str)

    # Seller type
    seller_str = clean(raw.get("seller_type_raw") or "").lower()
    data.seller_type = _map_seller_type(seller_str)

    data.colour = clean(raw.get("colour") or "")
    data.condition = clean(raw.get("condition") or "")
    data.location = clean(raw.get("location") or "")
    data.origin_country = clean(raw.get("origin_country") or "")

    return data


def _normalize_json_field(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return clean(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _parse_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = clean(str(value))
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Enum mapping helpers
# ---------------------------------------------------------------------------

def _map_fuel(s: str) -> str:
    if not s:
        return ""
    if any(w in s for w in ["benzyna", "petrol", "gasolin"]):
        return FuelType.PETROL.value
    if any(w in s for w in ["diesel", "olej nap"]):
        return FuelType.DIESEL.value
    if any(w in s for w in ["hybrid", "hybryd"]):
        return FuelType.HYBRID.value
    if any(w in s for w in ["elektr"]):
        return FuelType.ELECTRIC.value
    if "lpg" in s:
        return FuelType.LPG.value
    if "cng" in s:
        return FuelType.CNG.value
    return s


def _map_transmission(s: str) -> str:
    if not s:
        return ""
    if any(w in s for w in ["automat", "automatic"]):
        return Transmission.AUTOMATIC.value
    if any(w in s for w in ["manual", "ręczna", "mechaniczna"]):
        return Transmission.MANUAL.value
    return s


def _map_body_type(s: str) -> str:
    if not s:
        return ""
    mapping = {
        "sedan": BodyType.SEDAN.value,
        "hatchback": BodyType.HATCHBACK.value,
        "kompakt": BodyType.HATCHBACK.value,
        "kombi": BodyType.COMBI.value,
        "suv": BodyType.SUV.value,
        "coupe": BodyType.COUPE.value,
        "kabrio": BodyType.CABRIOLET.value,
        "van": BodyType.VAN.value,
        "minivan": BodyType.MINIBUS.value,
        "pickup": BodyType.PICKUP.value,
    }
    for key, val in mapping.items():
        if key in s:
            return val
    return s


def _map_seller_type(s: str) -> str:
    if not s:
        return SellerType.UNKNOWN.value
    if any(w in s for w in ["prywat", "private", "osoba"]):
        return SellerType.PRIVATE.value
    if any(w in s for w in ["dealer", "salon", "firma", "komisja"]):
        return SellerType.DEALER.value
    return SellerType.UNKNOWN.value
