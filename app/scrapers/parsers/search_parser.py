"""Otomoto Parser – Search results page parser.

Parses the HTML of an otomoto.pl search/listing page and returns
a list of raw dicts, one per listing card.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class SearchParser:
    """Extracts listing card data from an otomoto search results page."""

    # CSS selectors – update these if otomoto changes their markup
    _ARTICLE_SELECTOR = "article[data-id]"
    _NEXT_PAGE_SELECTOR = 'a[data-testid="pagination-step-forwards"]'

    def parse(self, soup: BeautifulSoup) -> list[dict]:
        """Return a list of raw listing dicts from the search results soup."""
        articles = soup.select(self._ARTICLE_SELECTOR)
        if not articles:
            # Fallback: try generic article tags
            articles = soup.find_all("article")
        logger.debug(f"Found {len(articles)} listing cards on page")
        results = []
        for article in articles:
            item = self._parse_card(article)
            if item:
                results.append(item)
        return results

    def has_next_page(self, soup: BeautifulSoup) -> bool:
        """Return True if a next-page link is present."""
        return bool(soup.select_one(self._NEXT_PAGE_SELECTOR))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_card(self, article: Tag) -> Optional[dict]:
        try:
            listing_id = article.get("data-id", "")
            url = self._extract_url(article)
            title = self._text(article, "h2") or self._text(article, "h3")
            price = self._text(article, '[data-testid="ad-price"]') or self._extract_price_fallback(article)
            year = self._extract_param(article, "Rok")
            mileage = self._extract_param(article, "Przebieg")
            fuel = self._extract_param(article, "Rodzaj paliwa") or self._extract_param(article, "Paliwo")
            thumbnail = self._extract_thumbnail(article)

            if not listing_id and not url:
                return None

            return {
                "id": listing_id,
                "url": url,
                "title": title,
                "price_raw": price,
                "year_raw": year,
                "mileage_raw": mileage,
                "fuel_raw": fuel,
                "thumbnail_url": thumbnail,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to parse card: {exc}")
            return None

    def _extract_url(self, article: Tag) -> str:
        link = article.select_one("h3 a") or article.select_one("h2 a") or article.select_one("a[href*='otomoto.pl']")
        if link:
            return link.get("href", "")
        # Try to find any link that looks like a listing URL
        for a in article.find_all("a", href=True):
            href = a["href"]
            if "oferta" in href or "/osobowe/" in href or "/motoryzacja/" in href:
                return href
        return ""

    def _text(self, tag: Tag, selector: str) -> str:
        el = tag.select_one(selector)
        return el.get_text(strip=True) if el else ""

    def _extract_price_fallback(self, article: Tag) -> str:
        """Find any element that looks like a PLN price."""
        text = article.get_text(" ", strip=True)
        match = re.search(r"(\d[\d\s]+)\s*PLN", text)
        return match.group(0) if match else ""

    def _extract_param(self, article: Tag, label: str) -> str:
        """Try to extract a parameter by its visible label text."""
        for dd in article.find_all("dd"):
            prev = dd.find_previous_sibling("dt")
            if prev and label.lower() in prev.get_text(strip=True).lower():
                return dd.get_text(strip=True)
        # Fallback: look for data-parameter attribute
        el = article.find(attrs={"data-parameter": True})
        if el:
            for li in article.find_all("li"):
                txt = li.get_text(strip=True)
                if label.lower() in txt.lower():
                    return txt
        return ""

    def _extract_thumbnail(self, article: Tag) -> str:
        img = article.select_one("img[src]") or article.select_one("img[data-src]")
        if not img:
            return ""
        return img.get("src") or img.get("data-src", "")
