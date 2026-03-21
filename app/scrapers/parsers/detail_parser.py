"""Otomoto Parser – Detail page parser.

Extracts detailed specs from an individual otomoto.pl listing page.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class DetailParser:
    """Extracts all spec fields from an otomoto detail listing page."""

    def parse(self, soup: BeautifulSoup) -> dict:
        """Return a raw dict of all extracted fields."""
        try:
            return {
                "title": self._get_title(soup),
                "price_raw": self._get_price(soup),
                "description": self._get_description(soup),
                "thumbnail_url": self._get_thumbnail(soup),
                "photos": self._get_photos(soup),
                "seller_type_raw": self._get_seller_type(soup),
                "location": self._get_location(soup),
                "published_at": self._get_published_at(soup),
                "source_category": self._get_source_category(soup),
                **self._get_params(soup),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Detail parse error: {exc}")
            return {}

    # ------------------------------------------------------------------
    # Field extractors
    # ------------------------------------------------------------------

    def _get_title(self, soup: BeautifulSoup) -> str:
        for sel in ['h1[data-testid="ad-title"]', "h1.offer-title", "h1"]:
            el = soup.select_one(sel)
            if el:
                return el.get_text(strip=True)
        return ""

    def _get_price(self, soup: BeautifulSoup) -> str:
        for sel in [
            '[data-testid="ad-price-container"]',
            ".offer-price",
            ".price-label",
            '[class*="price"]',
        ]:
            el = soup.select_one(sel)
            if el:
                return el.get_text(strip=True)
        return ""

    def _get_description(self, soup: BeautifulSoup) -> str:
        for sel in [
            '[data-testid="textblock"]',
            ".offer-description__description",
            "#description",
            ".description-content",
        ]:
            el = soup.select_one(sel)
            if el:
                return el.get_text(" ", strip=True)
        return ""

    def _get_thumbnail(self, soup: BeautifulSoup) -> str:
        for sel in [
            'img[data-testid="image-gallery-img"]',
            ".photo-item img",
            ".gallery-container img",
            "img[src*='otomoto']",
        ]:
            el = soup.select_one(sel)
            if el:
                return self._attr_text(el, "src") or self._attr_text(el, "data-src")
        return ""

    def _get_seller_type(self, soup: BeautifulSoup) -> str:
        for sel in [
            '[data-testid="seller-type"]',
            ".seller-box__seller-type",
            '[class*="seller-type"]',
        ]:
            el = soup.select_one(sel)
            if el:
                return el.get_text(strip=True)
        return ""

    def _get_location(self, soup: BeautifulSoup) -> str:
        for sel in [
            '[data-testid="seller-address"]',
            ".offer-meta__location",
            '[class*="location"]',
            ".seller-box__seller-address",
        ]:
            el = soup.select_one(sel)
            if el:
                return el.get_text(strip=True)
        return ""

    def _get_photos(self, soup: BeautifulSoup) -> list[str]:
        photos: list[str] = []
        for img in soup.select("img[src], img[data-src]"):
            src = self._attr_text(img, "src") or self._attr_text(img, "data-src")
            if src and src not in photos and ("img" in src or "photo" in src or "image" in src):
                photos.append(src)
        return photos[:50]

    def _get_published_at(self, soup: BeautifulSoup) -> str:
        for selector in ('meta[property="article:published_time"]', 'meta[name="datePublished"]'):
            el = soup.select_one(selector)
            content = self._attr_text(el, "content") if el else ""
            if content:
                return content

        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.get_text(strip=True))
            except json.JSONDecodeError:
                continue
            published = self._find_in_json(data, "datePublished")
            if published:
                return str(published)
        return ""

    def _get_source_category(self, soup: BeautifulSoup) -> str:
        breadcrumb = []
        for el in soup.select('[data-testid="breadcrumb"] a, nav[aria-label*="breadcrumb"] a, ol li a'):
            text = el.get_text(" ", strip=True)
            if text:
                breadcrumb.append(text)
        if breadcrumb:
            return " > ".join(breadcrumb)

        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.get_text(strip=True))
            except json.JSONDecodeError:
                continue
            category = self._find_in_json(data, "category")
            if category:
                return str(category)
        return ""

    def _get_params(self, soup: BeautifulSoup) -> dict:
        """Extract the parameter table (Year, Mileage, Engine, etc.)."""
        params: dict = {}

        # Try structured parameter lists: <li data-testid="advert-details-item">
        for li in soup.select('[data-testid="advert-details-item"]'):
            key_el = li.select_one('[data-testid="advert-details-item-title"]')
            val_el = li.select_one('[data-testid="advert-details-item-value"]')
            if key_el and val_el:
                key = key_el.get_text(strip=True).lower()
                val = val_el.get_text(strip=True)
                params[key] = val

        # Fallback: dt/dd pairs anywhere in the document
        if not params:
            for dl in soup.find_all("dl"):
                dts = dl.find_all("dt")
                dds = dl.find_all("dd")
                for dt, dd in zip(dts, dds):
                    key = dt.get_text(strip=True).lower()
                    val = dd.get_text(strip=True)
                    if key:
                        params[key] = val

        # Normalise common polish param names to English keys
        mapping = {
            "rok produkcji": "year_raw",
            "rok": "year_raw",
            "przebieg": "mileage_raw",
            "pojemność skokowa": "engine_cc_raw",
            "moc": "power_hp_raw",
            "rodzaj paliwa": "fuel_raw",
            "paliwo": "fuel_raw",
            "skrzynia biegów": "transmission_raw",
            "nadwozie": "body_type_raw",
            "kolor": "colour",
            "stan": "condition",
            "kraj pochodzenia": "origin_country",
            "numer rejestracyjny pojazdu": "plate_hint",
            "typ": "body_type_raw",
        }
        normalised: dict = {}
        for k, v in params.items():
            mapped_key = mapping.get(k, k)
            normalised[mapped_key] = v

        normalised["raw_attributes_json"] = json.dumps(params, ensure_ascii=False, sort_keys=True)

        return normalised

    def _find_in_json(self, data, key: str):
        if isinstance(data, dict):
            if key in data:
                return data[key]
            for value in data.values():
                found = self._find_in_json(value, key)
                if found:
                    return found
        if isinstance(data, list):
            for item in data:
                found = self._find_in_json(item, key)
                if found:
                    return found
        return None

    @staticmethod
    def _attr_text(tag: Tag, name: str) -> str:
        value: Any = tag.get(name, "")
        return value if isinstance(value, str) else ""
