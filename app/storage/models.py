"""Otomoto Parser – SQLAlchemy ORM model for a single listing."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Listing(Base):
    """One otomoto.pl car listing."""

    __tablename__ = "listings"
    __table_args__ = (
        Index("ix_listings_url", "url"),
        Index("ix_listings_price_pln", "price_pln"),
        Index("ix_listings_year", "year"),
        Index("ix_listings_mileage_km", "mileage_km"),
        Index("ix_listings_fuel_type", "fuel_type"),
        Index("ix_listings_transmission", "transmission"),
        Index("ix_listings_seller_type", "seller_type"),
        Index("ix_listings_body_type", "body_type"),
        Index("ix_listings_updated_at", "updated_at"),
    )

    # Primary key = otomoto listing ID (string from the site)
    otomoto_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # URL
    url: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    # Core
    title: Mapped[str] = mapped_column(String(256), default="")
    price_pln: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mileage_km: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Drivetrain
    fuel_type: Mapped[str] = mapped_column(String(32), default="")
    transmission: Mapped[str] = mapped_column(String(32), default="")
    engine_cc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    power_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Body
    body_type: Mapped[str] = mapped_column(String(64), default="")
    colour: Mapped[str] = mapped_column(String(64), default="")
    condition: Mapped[str] = mapped_column(String(32), default="")

    # Seller
    seller_type: Mapped[str] = mapped_column(String(32), default="")
    location: Mapped[str] = mapped_column(String(128), default="")

    # Content
    description: Mapped[str] = mapped_column(Text, default="")
    thumbnail_url: Mapped[str] = mapped_column(String(512), default="")
    origin_country: Mapped[str] = mapped_column(String(64), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    photos_json: Mapped[str] = mapped_column(Text, default="")
    source_category: Mapped[str] = mapped_column(String(256), default="")
    raw_attributes_json: Mapped[str] = mapped_column(Text, default="")

    # Meta
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Listing id={self.otomoto_id!r} title={self.title!r} price={self.price_pln}>"
