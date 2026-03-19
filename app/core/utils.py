"""Otomoto Parser – Shared utility helpers."""
from __future__ import annotations

import logging
import random
import re
import time
import unicodedata
from functools import wraps
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlsplit, urlunsplit

from tenacity import retry, stop_after_attempt, wait_fixed, RetryError  # noqa: F401


# ---------------------------------------------------------------------------
# Text / value parsers
# ---------------------------------------------------------------------------

def parse_price(text: str | None) -> Optional[int]:
    """Extract integer PLN price from strings like '125 900 PLN' or '125900'."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_mileage(text: str | None) -> Optional[int]:
    """Extract integer km from strings like '125 430 km' or '125430km'."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_year(text: str | None) -> Optional[int]:
    """Extract a 4-digit year."""
    if not text:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group()) if match else None


def parse_engine_cc(text: str | None) -> Optional[int]:
    """Parse engine displacement, e.g. '1 998 cm³' → 1998."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_power_hp(text: str | None) -> Optional[int]:
    """Parse power, e.g. '190 KM' → 190."""
    if not text:
        return None
    hp_match = re.search(r"(\d+)\s*(KM|km|HP|hp)\b", text)
    if hp_match:
        return int(hp_match.group(1))

    kw_match = re.search(r"(\d+)\s*(kW|kw)\b", text)
    if kw_match:
        kw_value = int(kw_match.group(1))
        return round(kw_value * 1.34102)

    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to a safe lowercase slug, e.g. for filenames."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", text)


def clean(text: str | None) -> str:
    """Strip and collapse whitespace."""
    if not text:
        return ""
    return " ".join(text.split())


def normalize_listing_url(url: str | None) -> str:
    """Canonicalise a listing URL for stable deduplication."""
    if not url:
        return ""
    parsed = urlsplit(clean(url))
    query = parse_qs(parsed.query)
    kept_query = ""
    if "search" in query:
        kept_query = f"search={query['search'][0]}"
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, kept_query, ""))


def extract_otomoto_id(url: str | None) -> str:
    """Extract a stable otomoto listing id from a URL when possible."""
    normalized = normalize_listing_url(url)
    if not normalized:
        return ""

    parsed = urlsplit(normalized)
    query = parse_qs(parsed.query)
    for key in ("id", "ad_id", "listing_id"):
        values = query.get(key)
        if values and values[0]:
            return values[0].strip()

    path = parsed.path
    match = re.search(r"(ID[0-9A-Za-z]+)", path)
    if match:
        return match.group(1)

    parts = [part for part in path.split("/") if part]
    if parts:
        tail = parts[-1]
        if re.fullmatch(r"[0-9A-Za-z]{8,}", tail):
            return tail

    return ""


# ---------------------------------------------------------------------------
# Retry decorator (thin wrapper over tenacity)
# ---------------------------------------------------------------------------

def with_retry(
    attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    jitter: float = 0.25,
    logger_name: str | None = None,
) -> Callable:
    """Decorator: retry with exponential backoff and optional logging."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            retry_logger = logging.getLogger(logger_name or fn.__module__)
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt < attempts:
                        sleep_for = delay * (backoff ** (attempt - 1))
                        sleep_for += random.uniform(0, sleep_for * jitter)
                        retry_logger.warning(
                            "Retrying %s after error (%s/%s): %s",
                            fn.__name__,
                            attempt,
                            attempts,
                            exc,
                        )
                        time.sleep(sleep_for)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator
