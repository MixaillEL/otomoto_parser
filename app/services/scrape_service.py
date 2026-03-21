"""Otomoto Parser – Core scraping orchestration service."""
from __future__ import annotations

import logging
from typing import Optional, Protocol, TypedDict

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from app.scrapers.search_scraper import SearchScraper
from app.services.listing_pipeline import DetailScraperLike, ListingPipeline, ListingRepositoryLike
from app.services.url_builder import build_search_url

logger = logging.getLogger(__name__)


class SearchScraperLike(Protocol):
    def scrape_all(self, base_url: str, max_pages: Optional[int] = None) -> list[dict]:
        ...


class ScrapeRunContext(TypedDict):
    label: str
    url: str
    effective_max: Optional[int]


class ScrapeService:
    """Orchestrates a complete search → detail → upsert pipeline."""

    def __init__(
        self,
        search_scraper: SearchScraperLike,
        detail_scraper: DetailScraperLike,
        repo: ListingRepositoryLike,
        skip_detail: bool = False,
    ) -> None:
        self._search = search_scraper
        self._pipeline = ListingPipeline(
            detail_scraper=detail_scraper,
            repo=repo,
            skip_detail=skip_detail,
        )

    def run(self, config: dict, max_pages: Optional[int] = None) -> int:
        """Run a single named search end-to-end.

        Args:
            config: Dict from searches.yaml (filters + metadata).
            max_pages: Override global max-pages for this run.

        Returns:
            Number of listings upserted.
        """
        context = self._build_run_context(config, max_pages)
        logger.info(f"Starting scrape: [{context['label']}] → {context['url']}")

        raw_cards = self._collect_cards(context)

        if not raw_cards:
            return 0

        upserted = self._process_cards(raw_cards, context["label"])
        logger.info(f"Done [{context['label']}]: {upserted} listings upserted to DB")
        return upserted

    def _build_run_context(self, config: dict, max_pages: Optional[int]) -> ScrapeRunContext:
        label = config.get("label") or config.get("brand") or "search"
        per_search_pages = config.get("max_pages")
        return {
            "label": label,
            "url": build_search_url(config),
            "effective_max": max_pages or per_search_pages,
        }

    def _collect_cards(self, context: ScrapeRunContext) -> list[dict]:
        raw_cards = self._search.scrape_all(
            context["url"],
            max_pages=context["effective_max"],
        )
        logger.info(f"Search complete: {len(raw_cards)} listing stubs collected")
        return raw_cards

    def _process_cards(self, raw_cards: list[dict], label: str) -> int:
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
                if self._pipeline.process(card):
                    upserted += 1
                progress.advance(task)
        return upserted
