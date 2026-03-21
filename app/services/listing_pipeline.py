"""Otomoto Parser – Per-listing scrape/normalize/persist pipeline."""
from __future__ import annotations

import logging
from typing import Protocol

from app.scrapers.normalizers import ListingData, normalize_listing

logger = logging.getLogger(__name__)


class DetailScraperLike(Protocol):
    def scrape(self, url: str) -> dict:
        ...


class ListingRepositoryLike(Protocol):
    def upsert(self, data: ListingData) -> object:
        ...


class ListingPipeline:
    """Handles one listing card from optional detail fetch to persistence."""

    def __init__(
        self,
        detail_scraper: DetailScraperLike,
        repo: ListingRepositoryLike,
        skip_detail: bool = False,
    ) -> None:
        self._detail = detail_scraper
        self._repo = repo
        self._skip_detail = skip_detail

    def process(self, card: dict) -> bool:
        data = self.normalize(card)
        return self.persist(data)

    def normalize(self, card: dict) -> ListingData:
        detail = self.fetch_detail(card)
        merged = {**card, **detail}
        return normalize_listing(merged)

    def fetch_detail(self, card: dict) -> dict:
        if self._skip_detail:
            return {}
        url = card.get("url")
        if not isinstance(url, str) or not url:
            return {}
        return self._detail.scrape(url)

    def persist(self, data: ListingData) -> bool:
        if not data.otomoto_id:
            logger.warning("Skipping listing without otomoto_id: %s", data.url or data.title)
            return False
        self._repo.upsert(data)
        return True
