"""Otomoto Parser – HTTP client using requests."""
from __future__ import annotations

import logging
import random
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.settings import settings

logger = logging.getLogger(__name__)

# A small pool of realistic User-Agent strings
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

_BLOCK_MARKERS = (
    "captcha",
    "verify you are human",
    "access denied",
    "temporarily blocked",
    "cloudflare",
    "unusual traffic",
)


class AntiBotBlockedError(RuntimeError):
    """Raised when the target site appears to have blocked scraping."""


class OtomotoHttpClient:
    """Polite HTTP client with retries and configurable delay."""

    BASE_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.otomoto.pl/",
    }

    def __init__(
        self,
        delay_ms: Optional[int] = None,
        user_agent: Optional[str] = None,
        retries: int = 3,
        backoff: float = 1.5,
    ) -> None:
        self._delay_ms = delay_ms if delay_ms is not None else settings.request_delay_ms
        self._user_agent = user_agent or settings.user_agent
        self._timeout_s = settings.http_timeout_s
        self._jitter_ratio = settings.request_jitter_ratio
        self._session = self._build_session(retries, backoff)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, url: str, **kwargs) -> BeautifulSoup:
        """Fetch *url* and return a parsed BeautifulSoup tree."""
        response = self.get_raw(url, **kwargs)
        return BeautifulSoup(response.text, "lxml")

    def get_raw(self, url: str, **kwargs) -> requests.Response:
        """Fetch *url* and return the raw Response object."""
        self._throttle()
        ua = self._user_agent or random.choice(_USER_AGENTS)
        headers = {**self.BASE_HEADERS, "User-Agent": ua}
        timeout = kwargs.pop("timeout", self._random_timeout())
        logger.debug("HTTP GET %s ua=%s timeout=%ss", url, ua, timeout)
        started = time.perf_counter()
        response = self._session.get(url, headers=headers, timeout=timeout, **kwargs)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info("HTTP %s %s in %sms", response.status_code, url, elapsed_ms)
        self._raise_for_block(response)
        response.raise_for_status()
        return response

    def close(self) -> None:
        self._session.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_session(self, retries: int, backoff: float) -> requests.Session:
        session = requests.Session()
        retry_config = Retry(
            total=retries,
            backoff_factor=backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry_config)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _throttle(self) -> None:
        """Sleep for the configured delay plus a small random jitter."""
        base = self._delay_ms / 1000.0
        jitter = random.uniform(0, base * self._jitter_ratio)
        time.sleep(base + jitter)

    def _random_timeout(self) -> float:
        jitter = random.uniform(0, max(1.0, self._timeout_s * 0.15))
        return self._timeout_s + jitter

    def _raise_for_block(self, response: requests.Response) -> None:
        if response.status_code in (403, 429):
            self._cooldown(response.status_code)
            raise AntiBotBlockedError(f"Blocked with HTTP {response.status_code} for {response.url}")

        body = response.text.lower()
        if any(marker in body for marker in _BLOCK_MARKERS):
            self._cooldown(response.status_code)
            raise AntiBotBlockedError(f"Block markers detected in response for {response.url}")

    def _cooldown(self, status_code: int) -> None:
        penalty = 2.0 if status_code == 403 else 3.5 if status_code == 429 else 1.5
        delay = (self._delay_ms / 1000.0) + penalty
        logger.warning("Anti-bot cooldown triggered for status=%s sleep=%.2fs", status_code, delay)
        time.sleep(delay)

    def __enter__(self) -> "OtomotoHttpClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
