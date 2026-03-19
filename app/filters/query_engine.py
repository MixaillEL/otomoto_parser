"""Otomoto Parser – In-memory / SQL query engine for listing filters."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.storage.models import Listing

logger = logging.getLogger(__name__)


class QueryEngine:
    """Builds filtered SQLAlchemy SELECT statements for Listing."""

    SUPPORTED_FILTERS = {
        "price_min", "price_max",
        "year_min", "year_max",
        "mileage_max",
        "fuel_type",
        "transmission",
        "seller_type",
        "body_type",
        "colour",
        "condition",
        "location",
    }

    def build_query(self, filters: dict[str, Any]):
        """Return a SQLAlchemy select statement with filters applied."""
        stmt = select(Listing)

        if v := filters.get("price_min"):
            stmt = stmt.where(Listing.price_pln >= int(v))
        if v := filters.get("price_max"):
            stmt = stmt.where(Listing.price_pln <= int(v))
        if v := filters.get("year_min"):
            stmt = stmt.where(Listing.year >= int(v))
        if v := filters.get("year_max"):
            stmt = stmt.where(Listing.year <= int(v))
        if v := filters.get("mileage_max"):
            stmt = stmt.where(Listing.mileage_km <= int(v))
        if v := filters.get("fuel_type"):
            stmt = stmt.where(Listing.fuel_type == str(v))
        if v := filters.get("transmission"):
            stmt = stmt.where(Listing.transmission == str(v))
        if v := filters.get("seller_type"):
            stmt = stmt.where(Listing.seller_type == str(v))
        if v := filters.get("body_type"):
            stmt = stmt.where(Listing.body_type == str(v))
        if v := filters.get("colour"):
            stmt = stmt.where(Listing.colour.ilike(f"%{v}%"))
        if v := filters.get("condition"):
            stmt = stmt.where(Listing.condition == str(v))
        if v := filters.get("location"):
            stmt = stmt.where(Listing.location.ilike(f"%{v}%"))

        unsupported = set(filters) - self.SUPPORTED_FILTERS
        if unsupported:
            logger.warning(f"Unknown filter keys: {unsupported}")

        return stmt

    def execute(self, session: Session, filters: dict[str, Any]) -> list[Listing]:
        """Run the filtered query against *session* and return results."""
        stmt = self.build_query(filters)
        return list(session.scalars(stmt).all())
