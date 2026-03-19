"""Otomoto Parser – Core scraping orchestration service."""
from __future__ import annotations

import logging
from typing import Optional

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from app.scrapers.detail_scraper import DetailScraper
from app.scrapers.normalizers import normalize_listing
from app.scrapers.search_scraper import SearchScraper
from app.services.url_builder import build_search_url
from app.storage.repository import ListingRepository

logger = logging.getLogger(__name__)


class ScrapeService:
    """Orchestrates a complete search → detail → upsert pipeline."""

    def __init__(
        self,
        search_scraper: SearchScraper,
        detail_scraper: DetailScraper,
        repo: ListingRepository,
        skip_detail: bool = False,
    ) -> None:
        self._search = search_scraper
        self._detail = detail_scraper
        self._repo = repo
        self._skip_detail = skip_detail  # useful for quick smoke-tests

    def run(self, search_config: dict, max_pages: Optional[int] = None) -> int:
        """Run a single named search end-to-end.

        Args:
            search_config: Dict from searches.yaml (filters + metadata).
            max_pages: Override global max-pages for this run.

        Returns:
            Number of listings upserted.
        """
        label = search_config.get("label") or search_config.get("brand") or "search"
        per_search_pages = search_config.get("max_pages")
        effective_max = max_pages or per_search_pages

        url = build_search_url(search_config)
        logger.info(f"Starting scrape: [{label}] → {url}")

        # 1️⃣ Collect listing stubs from search results pages
        raw_cards = self._search.scrape_all(url, max_pages=effective_max)
        logger.info(f"Search complete: {len(raw_cards)} listing stubs collected")

        if not raw_cards:
            return 0

        # 2️⃣ For each card, optionally fetch full detail page
        upserted = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task(f"[{label}] Scraping details…", total=len(raw_cards))
            for card in raw_cards:
                detail: dict = {}
                if not self._skip_detail and card.get("url"):
                    detail = self._detail.scrape(card["url"])

                merged = {**card, **detail}
                data = normalize_listing(merged)

                if data.otomoto_id:
                    self._repo.upsert(data)
                    upserted += 1
                else:
                    logger.warning("Skipping listing without otomoto_id: %s", data.url or data.title)

                progress.advance(task)

        logger.info(f"Done [{label}]: {upserted} listings upserted to DB")
        return upserted
