"""Otomoto Parser – Runs all configured searches from searches.yaml."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from app.services.scrape_service import ScrapeService

logger = logging.getLogger(__name__)


class SearchService:
    """Loads searches.yaml and dispatches each search to ScrapeService."""

    def __init__(self, scrape_service: ScrapeService) -> None:
        self._scrape = scrape_service

    def run_all(
        self,
        config_path: Path,
        only: Optional[str] = None,
        max_pages: Optional[int] = None,
        skip_detail: bool = False,
    ) -> dict[str, int]:
        """Run all searches defined in *config_path*.

        Args:
            config_path: Path to searches.yaml.
            only: If set, run only the search with this key.
            max_pages: Global page limit override.
            skip_detail: If True, skip individual detail-page scraping.

        Returns:
            Dict mapping search key → number of listings upserted.
        """
        searches = self._load(config_path)
        if not searches:
            logger.warning(f"No searches defined in {config_path}")
            return {}

        if only:
            if only not in searches:
                raise ValueError(f"Search '{only}' not found in {config_path}. "
                                 f"Available: {list(searches.keys())}")
            searches = {only: searches[only]}

        results: dict[str, int] = {}
        total_searches = len(searches)
        for idx, (name, config) in enumerate(searches.items(), 1):
            logger.info(f"[{idx}/{total_searches}] Running search: {name!r}")
            try:
                count = self._scrape.run(
                    config,
                    max_pages=max_pages,
                )
                results[name] = count
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Search '{name}' failed: {exc}")
                results[name] = 0

        total = sum(results.values())
        logger.info(f"All searches complete. Total upserted: {total}")
        return results

    @staticmethod
    def _load(config_path: Path) -> dict:
        if not config_path.exists():
            raise FileNotFoundError(f"searches.yaml not found: {config_path}")
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("searches", {})
