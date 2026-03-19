"""Otomoto Parser – Search URL builder.

Maps a search config dict (from searches.yaml) to a valid otomoto.pl URL.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode, urljoin

from app.core.enums import BodyType, FuelType, SortOrder, Transmission

logger = logging.getLogger(__name__)

# Otomoto base search URL
_BASE = "https://www.otomoto.pl/osobowe"

# Maps YAML fuel_type → otomoto filter value
_FUEL_MAP: dict[str, str] = {
    "petrol": "petrol",
    "diesel": "diesel",
    "hybrid": "hybrid",
    "electric": "electric",
    "lpg": "lpg",
    "cng": "cng",
}

# Maps YAML transmission → otomoto filter value
_TRANS_MAP: dict[str, str] = {
    "manual": "manual",
    "automatic": "automatic",
}

# Maps YAML body_type → otomoto URL path segment
_BODY_PATH_MAP: dict[str, str] = {
    "sedan": "sedan",
    "suv": "suv-crossover",
    "hatchback": "kompakt",
    "combi": "kombi",
    "coupe": "coupe",
    "cabriolet": "kabriolet",
    "van": "minivan",
    "pickup": "pickup",
}

# Maps YAML sort → otomoto sort value
_SORT_MAP: dict[str, str] = {
    "price_asc": "filter_float_price%3Aasc",
    "price_desc": "filter_float_price%3Adesc",
    "latest": "created_at%3Adesc",
    "mileage_asc": "filter_float_mileage%3Aasc",
}


def build_search_url(params: dict[str, Any]) -> str:
    """Build an otomoto.pl search URL from a YAML search config dict.

    Args:
        params: Dict with optional keys: brand, model, year_from, year_to,
                price_from, price_to, mileage_max, fuel_type, transmission,
                body_type, sort, max_pages (ignored here).

    Returns:
        A fully-formed otomoto search URL string.
    """
    # Build path: /osobowe[/brand[/model]][/body_type]
    parts = [_BASE]

    brand: str = (params.get("brand") or "").strip()
    model: str = (params.get("model") or "").strip()
    body_type: str = (params.get("body_type") or "").strip().lower()

    if brand:
        parts.append(_slugify_brand(brand))
        if model:
            parts.append(_slugify_model(model))
    elif body_type and body_type in _BODY_PATH_MAP:
        parts.append(_BODY_PATH_MAP[body_type])

    base_path = "/".join(parts)

    # Build query parameters
    query: dict[str, str] = {}

    # Body type as filter (when brand path already used)
    if brand and body_type and body_type in _BODY_PATH_MAP:
        query["search[filter_enum_body_type][]"] = _BODY_PATH_MAP.get(body_type, body_type)

    # Year range
    if params.get("year_from"):
        query["search[filter_float_year%3Afrom]"] = str(params["year_from"])
    if params.get("year_to"):
        query["search[filter_float_year%3Ato]"] = str(params["year_to"])

    # Price range
    if params.get("price_from"):
        query["search[filter_float_price%3Afrom]"] = str(params["price_from"])
    if params.get("price_to"):
        query["search[filter_float_price%3Ato]"] = str(params["price_to"])

    # Mileage
    if params.get("mileage_max"):
        query["search[filter_float_mileage%3Ato]"] = str(params["mileage_max"])

    # Fuel type
    fuel = _FUEL_MAP.get((params.get("fuel_type") or "").strip().lower())
    if fuel:
        query["search[filter_enum_fuel_type][]"] = fuel

    # Transmission
    trans = _TRANS_MAP.get((params.get("transmission") or "").strip().lower())
    if trans:
        query["search[filter_enum_gearbox][]"] = trans

    # Sort order
    sort_key = (params.get("sort") or "latest").strip().lower()
    sort_val = _SORT_MAP.get(sort_key, _SORT_MAP["latest"])
    query["search[order]"] = sort_val

    # Always include new & used
    query["search[advanced_search_expanded]"] = "true"

    qs = "&".join(f"{k}={v}" for k, v in query.items())
    url = f"{base_path}/?{qs}" if qs else f"{base_path}/"

    logger.debug(f"Built URL: {url}")
    return url


def _slugify_brand(brand: str) -> str:
    """Convert brand name to otomoto URL slug (lowercase, hyphenated)."""
    return brand.strip().lower().replace(" ", "-")


def _slugify_model(model: str) -> str:
    """Convert model name to otomoto URL slug."""
    import re
    slug = model.strip().lower()
    slug = re.sub(r"[^a-z0-9\-]", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug
