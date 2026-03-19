import sys
import types
import unittest
from pathlib import Path

import app.core.settings as settings_module
from app.clients.http_client import AntiBotBlockedError
from app.clients.resilient_client import ResilientOtomotoClient
from app.core.utils import extract_otomoto_id, normalize_listing_url, parse_power_hp, with_retry
from app.scrapers.normalizers import ListingData, normalize_listing
from app.scrapers.parsers.detail_parser import DetailParser
from bs4 import BeautifulSoup

fake_repository_module = types.ModuleType("app.storage.repository")
fake_repository_module.ListingRepository = object
sys.modules.setdefault("app.storage.repository", fake_repository_module)

from app.services.scrape_service import ScrapeService


class SettingsTests(unittest.TestCase):
    def test_env_file_points_to_project_config(self) -> None:
        expected = Path(r"c:\My Project\otomoto_parser\config\.env").resolve()
        self.assertEqual(settings_module._ENV_FILE.resolve(), expected)


class ParsePowerTests(unittest.TestCase):
    def test_prefers_explicit_hp_over_kw(self) -> None:
        self.assertEqual(parse_power_hp("140 kW (190 KM)"), 190)

    def test_converts_kw_to_hp_when_needed(self) -> None:
        self.assertEqual(parse_power_hp("150 kW"), 201)


class IdentityNormalizationTests(unittest.TestCase):
    def test_normalize_listing_url_drops_tracking_query(self) -> None:
        raw = "https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID6G123.html?utm_source=x&page=2#gallery"
        self.assertEqual(
            normalize_listing_url(raw),
            "https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID6G123.html",
        )

    def test_extract_otomoto_id_from_url(self) -> None:
        url = "https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID6G123.html"
        self.assertEqual(extract_otomoto_id(url), "ID6G123")

    def test_normalize_listing_uses_url_as_id_fallback(self) -> None:
        data = normalize_listing({
            "id": "",
            "url": "https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID6G123.html?utm_source=x",
        })
        self.assertEqual(data.otomoto_id, "ID6G123")
        self.assertEqual(
            data.url,
            "https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID6G123.html",
        )
        self.assertEqual(data.source_category, "")

    def test_normalize_listing_stores_extra_metadata(self) -> None:
        data = normalize_listing({
            "id": "ID123",
            "url": "https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID123.html",
            "published_at": "2026-03-19T12:34:56Z",
            "photos": ["https://img.example/1.jpg", "https://img.example/2.jpg"],
            "source_category": "Osobowe > BMW",
            "raw_attributes_json": {"rok": "2020", "paliwo": "Benzyna"},
        })
        self.assertEqual(data.source_category, "Osobowe > BMW")
        self.assertIn('"rok": "2020"', data.raw_attributes_json)
        self.assertIn("https://img.example/1.jpg", data.photos_json)
        self.assertEqual(data.published_at.isoformat(), "2026-03-19T12:34:56+00:00")


class DetailParserTests(unittest.TestCase):
    def test_extracts_extended_fields(self) -> None:
        soup = BeautifulSoup(
            """
            <html>
              <head>
                <meta property="article:published_time" content="2026-03-19T12:34:56Z" />
                <script type="application/ld+json">
                  {"category":"Osobowe > BMW","datePublished":"2026-03-19T12:34:56Z"}
                </script>
              </head>
              <body>
                <nav aria-label="breadcrumb"><a>Osobowe</a><a>BMW</a></nav>
                <h1 data-testid="ad-title">BMW 530d</h1>
                <div data-testid="ad-price-container">125 900 PLN</div>
                <div data-testid="textblock">Opis auta</div>
                <img data-testid="image-gallery-img" src="https://img.example/cover.jpg" />
                <img src="https://img.example/1.jpg" />
                <img src="https://img.example/2.jpg" />
                <div data-testid="seller-address">Warszawa</div>
                <ul>
                  <li data-testid="advert-details-item">
                    <span data-testid="advert-details-item-title">Rok produkcji</span>
                    <span data-testid="advert-details-item-value">2020</span>
                  </li>
                </ul>
              </body>
            </html>
            """,
            "lxml",
        )
        result = DetailParser().parse(soup)
        self.assertEqual(result["published_at"], "2026-03-19T12:34:56Z")
        self.assertEqual(result["source_category"], "Osobowe > BMW")
        self.assertEqual(result["photos"][0], "https://img.example/cover.jpg")
        self.assertIn('"rok produkcji": "2020"', result["raw_attributes_json"])


class RetryTests(unittest.TestCase):
    def test_with_retry_retries_before_success(self) -> None:
        attempts = {"count": 0}

        @with_retry(attempts=3, delay=0.0, jitter=0.0)
        def flaky():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("boom")
            return "ok"

        self.assertEqual(flaky(), "ok")
        self.assertEqual(attempts["count"], 3)


class ResilientClientTests(unittest.TestCase):
    def test_falls_back_to_browser_when_http_blocked(self) -> None:
        client = ResilientOtomotoClient(
            http_client=_BlockedHttpClient(),
            browser_client=_FakeBrowserClient(),
        )

        result = client.get("https://example.com/listing")

        self.assertEqual(result, "browser-soup")


class ScrapeServiceTests(unittest.TestCase):
    def test_skips_cards_without_otomoto_id(self) -> None:
        search_scraper = _FakeSearchScraper([{"url": "https://example.com/oferta/1", "title": "No id"}])
        detail_scraper = _FakeDetailScraper({})
        repo = _FakeRepository()
        service = ScrapeService(search_scraper, detail_scraper, repo)

        upserted = service.run({"label": "test"})

        self.assertEqual(upserted, 0)
        self.assertEqual(repo.saved, [])


class _FakeSearchScraper:
    def __init__(self, cards):
        self._cards = cards

    def scrape_all(self, base_url: str, max_pages=None):
        return list(self._cards)


class _FakeDetailScraper:
    def __init__(self, result):
        self._result = result

    def scrape(self, url: str):
        return dict(self._result)


class _FakeRepository:
    def __init__(self):
        self.saved: list[ListingData] = []

    def upsert(self, data: ListingData):
        self.saved.append(data)
        return data


class _BlockedHttpClient:
    def get(self, url: str, **kwargs):
        raise AntiBotBlockedError(f"blocked: {url}")

    def close(self) -> None:
        return None


class _FakeBrowserClient:
    def __init__(self):
        self.calls = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        return "browser-soup"

    def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
