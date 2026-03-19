"""Otomoto Parser – Search results scraper (paginates listing pages)."""
from __future__ import annotations

import logging
from typing import Optional

from app.core.settings import settings
from app.core.utils import with_retry
from app.scrapers.parsers.search_parser import SearchParser

logger = logging.getLogger(__name__)


class SearchScraper:
    """Fetches and parses paginated otomoto search results."""

    def __init__(self, client) -> None:
        """
        Args:
            client: OtomotoHttpClient or OtomotoBrowserClient instance.
        """
        self._client = client
        self._parser = SearchParser()

    def scrape_all(
        self,
        base_url: str,
        max_pages: Optional[int] = None,
    ) -> list[dict]:
        """Paginate *base_url* and return all raw listing dicts found.

        Args:
            base_url: The first-page search URL (already contains filters).
            max_pages: Stop after this many pages. Falls back to settings.max_pages,
                       then to unlimited (100 as safety cap).
        """
        limit = max_pages or settings.max_pages or 100
        all_items: list[dict] = []
        current_url: Optional[str] = base_url

        for page_num in range(1, limit + 1):
            if not current_url:
                break

            logger.info(f"Scraping search page {page_num}: {current_url}")
            soup = self._fetch(current_url)
            if soup is None:
                logger.warning(f"Failed to fetch page {page_num}, stopping pagination")
                break

            items = self._parser.parse(soup)
            if not items:
                logger.info(f"No listings found on page {page_num}, stopping")
                break

            all_items.extend(items)
            logger.info(f"Page {page_num}: {len(items)} listings (total: {len(all_items)})")

            if not self._parser.has_next_page(soup):
                logger.info("No next page detected, pagination complete")
                break

            current_url = self._next_url(base_url, page_num + 1)

        return all_items

    def scrape_page(self, url: str) -> list[dict]:
        """Scrape a single page without pagination."""
        soup = self._fetch(url)
        return self._parser.parse(soup) if soup else []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @with_retry(
        attempts=settings.retry_attempts,
        delay=settings.retry_base_delay_s,
        logger_name=__name__,
    )
    def _fetch(self, url: str):
        try:
            return self._client.get(url)
        except Exception as exc:
            logger.warning(f"HTTP error fetching {url}: {exc}")
            raise

    @staticmethod
    def _next_url(base_url: str, page: int) -> str:
        """Append or replace the ?page= query parameter."""
        import re
        if "page=" in base_url:
            return re.sub(r"page=\d+", f"page={page}", base_url)
        connector = "&" if "?" in base_url else "?"
        return f"{base_url}{connector}page={page}"
