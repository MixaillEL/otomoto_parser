"""Otomoto Parser – Individual listing detail scraper."""
from __future__ import annotations

import logging

from app.core.settings import settings
from app.core.utils import with_retry
from app.scrapers.parsers.detail_parser import DetailParser

logger = logging.getLogger(__name__)


class DetailScraper:
    """Fetches and parses a single otomoto listing detail page."""

    def __init__(self, client) -> None:
        """
        Args:
            client: OtomotoHttpClient or OtomotoBrowserClient instance.
        """
        self._client = client
        self._parser = DetailParser()

    def scrape(self, url: str) -> dict:
        """Fetch and parse the detail page at *url*.

        Returns:
            Raw dict of extracted fields, or {} on failure.
        """
        try:
            soup = self._fetch(url)
            if soup is None:
                return {}
            result = self._parser.parse(soup)
            logger.debug(f"Parsed detail page: {url} → {len(result)} fields")
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Could not scrape detail page {url}: {exc}")
            return {}

    @with_retry(
        attempts=settings.retry_attempts,
        delay=settings.retry_base_delay_s,
        logger_name=__name__,
    )
    def _fetch(self, url: str):
        return self._client.get(url)
