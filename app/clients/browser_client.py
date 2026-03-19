"""Otomoto Parser – Optional Playwright browser client.

Activate by setting USE_BROWSER=true in config/.env.
Requires: pip install playwright && playwright install chromium
"""
from __future__ import annotations

import logging
import random
import time
from typing import Optional

from bs4 import BeautifulSoup

from app.core.settings import settings

logger = logging.getLogger(__name__)


class OtomotoBrowserClient:
    """Playwright-based client that renders JavaScript before parsing.

    Has the same public interface as OtomotoHttpClient so scrapers
    can use either client transparently.
    """

    def __init__(
        self,
        browser_type: Optional[str] = None,
        headless: bool = True,
    ) -> None:
        self._browser_type = browser_type or settings.browser_type
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._start()

    # ------------------------------------------------------------------
    # Public API (same surface as OtomotoHttpClient)
    # ------------------------------------------------------------------

    def get(self, url: str, **_) -> BeautifulSoup:
        """Navigate to *url* with Playwright and return a BeautifulSoup tree."""
        logger.debug("Browser GET %s", url)
        self._page.goto(url, wait_until="networkidle", timeout=30_000)
        time.sleep(random.uniform(0.4, 1.1))
        html = self._page.content()
        return BeautifulSoup(html, "lxml")

    def close(self) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start(self) -> None:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore

            self._playwright = sync_playwright().start()
            launcher = getattr(self._playwright, self._browser_type)
            self._browser = launcher.launch(headless=self._headless)
            self._context = self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="pl-PL",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={
                    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Referer": "https://www.otomoto.pl/",
                },
            )
            self._page = self._context.new_page()
            self._page.set_default_timeout(30_000)
            logger.info(f"Playwright browser started ({self._browser_type}, headless={self._headless})")
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright && playwright install"
            )

    def __enter__(self) -> "OtomotoBrowserClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
