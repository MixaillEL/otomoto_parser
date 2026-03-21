"""Otomoto Parser – Runs all configured searches from searches.yaml."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Protocol

import yaml

logger = logging.getLogger(__name__)


class ScrapeRunnerLike(Protocol):
    def run(self, config: dict, max_pages: Optional[int] = None) -> int:
        ...


class SearchService:
    """Loads searches.yaml and dispatches each search to ScrapeService."""

    def __init__(self, scrape_service: ScrapeRunnerLike) -> None:
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
        searches = self._select_searches(config_path, only)
        if not searches:
            logger.warning(f"No searches defined in {config_path}")
            return {}

        results = self._run_searches(searches, max_pages=max_pages)
        self._log_summary(results)
        return results

    def _select_searches(self, config_path: Path, only: Optional[str]) -> dict:
        searches = self._load(config_path)
        if not only:
            return searches
        if only not in searches:
            raise ValueError(
                f"Search '{only}' not found in {config_path}. Available: {list(searches.keys())}"
            )
        return {only: searches[only]}

    def _run_searches(self, searches: dict, max_pages: Optional[int]) -> dict[str, int]:
        results: dict[str, int] = {}
        total_searches = len(searches)
        for idx, (name, config) in enumerate(searches.items(), 1):
            logger.info(f"[{idx}/{total_searches}] Running search: {name!r}")
            results[name] = self._run_single_search(name, config, max_pages=max_pages)
        return results

    def _run_single_search(self, name: str, config: dict, max_pages: Optional[int]) -> int:
        try:
            return self._scrape.run(
                config,
                max_pages=max_pages,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Search '{name}' failed: {exc}")
            return 0

    @staticmethod
    def _log_summary(results: dict[str, int]) -> None:
        total = sum(results.values())
        logger.info(f"All searches complete. Total upserted: {total}")

    @staticmethod
    def _load(config_path: Path) -> dict:
        if not config_path.exists():
            raise FileNotFoundError(f"searches.yaml not found: {config_path}")
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("searches", {})
