"""Otomoto Parser – CSV exporter."""
from __future__ import annotations

import csv
import logging
from dataclasses import fields
from pathlib import Path

from app.storage.models import Listing

logger = logging.getLogger(__name__)

# Ordered column list for the CSV
_COLUMNS = [
    "otomoto_id", "title", "price_pln", "year", "mileage_km",
    "fuel_type", "transmission", "engine_cc", "power_hp",
    "body_type", "colour", "condition", "seller_type", "location",
    "origin_country", "published_at", "source_category", "raw_attributes_json",
    "photos_json", "url", "thumbnail_url", "scraped_at", "updated_at",
]


class CsvExporter:
    """Exports a list of Listing ORM objects to a CSV file."""

    def export(self, listings: list[Listing], path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for listing in listings:
                writer.writerow(self._to_row(listing))

        logger.info(f"CSV exported: {path} ({len(listings)} rows)")

    @staticmethod
    def _to_row(listing: Listing) -> dict:
        row = {}
        for col in _COLUMNS:
            val = getattr(listing, col, "")
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            row[col] = val if val is not None else ""
        return row
