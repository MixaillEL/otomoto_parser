"""Otomoto Parser – HTTP client with optional Playwright fallback."""
from __future__ import annotations

import logging
from typing import Optional

from bs4 import BeautifulSoup

from app.clients.browser_client import OtomotoBrowserClient
from app.clients.http_client import AntiBotBlockedError, OtomotoHttpClient
from app.core.settings import settings

logger = logging.getLogger(__name__)


class ResilientOtomotoClient:
    """Use HTTP by default and lazily switch to Playwright when blocked."""

    def __init__(
        self,
        http_client: Optional[OtomotoHttpClient] = None,
        browser_client: Optional[OtomotoBrowserClient] = None,
    ) -> None:
        self._http = http_client or OtomotoHttpClient(
            retries=settings.retry_attempts,
            backoff=settings.retry_base_delay_s,
        )
        self._browser = browser_client
        self._use_browser_only = settings.use_browser
        self._fallback_enabled = settings.browser_fallback_on_block

    def get(self, url: str, **kwargs) -> BeautifulSoup:
        if self._use_browser_only:
            return self._get_browser().get(url, **kwargs)

        try:
            return self._http.get(url, **kwargs)
        except AntiBotBlockedError as exc:
            if not self._fallback_enabled:
                raise
            logger.warning("HTTP client blocked, switching to Playwright fallback: %s", exc)
            return self._get_browser().get(url, **kwargs)

    def close(self) -> None:
        self._http.close()
        if self._browser:
            self._browser.close()

    def _get_browser(self) -> OtomotoBrowserClient:
        if self._browser is None:
            self._browser = OtomotoBrowserClient()
        return self._browser

    def __enter__(self) -> "ResilientOtomotoClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
