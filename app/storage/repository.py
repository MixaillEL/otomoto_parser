"""Otomoto Parser – Listing repository (upsert + query)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.filters.query_engine import QueryEngine
from app.scrapers.normalizers import ListingData
from app.storage.db import get_session
from app.storage.models import Listing

logger = logging.getLogger(__name__)


class ListingRepository:
    """Data-access layer for Listing records."""

    def __init__(self) -> None:
        self._query_engine = QueryEngine()

    def upsert(self, data: ListingData) -> Listing:
        """Insert a new listing or update an existing one by otomoto_id/url."""
        with get_session() as session:
            existing = self._find_existing(session, data)
            if existing:
                self._update_fields(existing, data)
                if data.otomoto_id and not existing.otomoto_id:
                    existing.otomoto_id = data.otomoto_id
                existing.updated_at = datetime.now(timezone.utc)
                logger.debug(f"Updated listing {existing.otomoto_id}")
                return existing
            else:
                listing = self._to_orm(data)
                session.add(listing)
                logger.debug(f"Inserted listing {data.otomoto_id}")
                return listing

    def find_all(self, filters: Optional[dict] = None, limit: Optional[int] = None) -> list[Listing]:
        """Return all listings matching optional *filters* dict.

        Supported filter keys:
            price_min, price_max, year_min, year_max, mileage_max,
            fuel_type, transmission, seller_type, body_type
        """
        with get_session() as session:
            stmt = self._query_engine.build_query(filters or {})
            if limit is not None:
                stmt = stmt.limit(max(int(limit), 1))
            return list(session.scalars(stmt).all())

    def count(self) -> int:
        """Return total count of listings in the DB."""
        with get_session() as session:
            return session.query(Listing).count()

    def find_by_id(self, otomoto_id: str) -> Optional[Listing]:
        with get_session() as session:
            return session.get(Listing, otomoto_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_orm(data: ListingData) -> Listing:
        return Listing(
            otomoto_id=data.otomoto_id,
            url=data.url,
            title=data.title,
            price_pln=data.price_pln,
            year=data.year,
            mileage_km=data.mileage_km,
            fuel_type=data.fuel_type,
            transmission=data.transmission,
            engine_cc=data.engine_cc,
            power_hp=data.power_hp,
            body_type=data.body_type,
            colour=data.colour,
            condition=data.condition,
            seller_type=data.seller_type,
            location=data.location,
            description=data.description,
            thumbnail_url=data.thumbnail_url,
            origin_country=data.origin_country,
            published_at=data.published_at,
            photos_json=data.photos_json,
            source_category=data.source_category,
            raw_attributes_json=data.raw_attributes_json,
            scraped_at=data.scraped_at,
            updated_at=data.scraped_at,
        )

    @staticmethod
    def _update_fields(listing: Listing, data: ListingData) -> None:
        for field in (
            "url", "title", "price_pln", "year", "mileage_km",
            "fuel_type", "transmission", "engine_cc", "power_hp",
            "body_type", "colour", "condition", "seller_type",
            "location", "description", "thumbnail_url", "origin_country",
            "published_at", "photos_json", "source_category", "raw_attributes_json",
        ):
            val = getattr(data, field, None)
            if val is not None and val != "":
                setattr(listing, field, val)

    @staticmethod
    def _find_existing(session: Session, data: ListingData) -> Optional[Listing]:
        if data.otomoto_id:
            existing = session.get(Listing, data.otomoto_id)
            if existing:
                return existing
        if data.url:
            return session.scalar(select(Listing).where(Listing.url == data.url))
        return None
