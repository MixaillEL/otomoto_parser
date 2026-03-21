import csv
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import app.core.settings as settings_module
from app.clients.http_client import AntiBotBlockedError
from app.clients.resilient_client import ResilientOtomotoClient
from app.core.utils import extract_otomoto_id, normalize_listing_url, parse_power_hp, with_retry
from app.filters.query_engine import QueryEngine
from app.scrapers.normalizers import ListingData, normalize_listing
from app.scrapers.parsers.detail_parser import DetailParser
from app.services.export_service import ExportService
from app.services.listing_pipeline import ListingPipeline
from app.services.search_service import SearchService
from bs4 import BeautifulSoup
from openpyxl import load_workbook

fake_repository_module = types.ModuleType("app.storage.repository")
setattr(fake_repository_module, "ListingRepository", object)
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
        self.assertIsNotNone(data.published_at)
        published_at = data.published_at
        assert published_at is not None
        self.assertEqual(published_at.isoformat(), "2026-03-19T12:34:56+00:00")


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

        self.assertIsInstance(result, BeautifulSoup)


class ScrapeServiceTests(unittest.TestCase):
    def test_skips_cards_without_otomoto_id(self) -> None:
        search_scraper = _FakeSearchScraper([{"url": "https://example.com/oferta/1", "title": "No id"}])
        detail_scraper = _FakeDetailScraper({})
        repo = _FakeRepository()
        service = ScrapeService(search_scraper, detail_scraper, repo)

        upserted = service.run({"label": "test"})

        self.assertEqual(upserted, 0)
        self.assertEqual(repo.saved, [])

    def test_processes_multiple_cards_and_counts_only_valid_upserts(self) -> None:
        search_scraper = _FakeSearchScraper([
            {
                "url": "https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID100.html",
                "title": "BMW 520d",
                "price_raw": "99 900 PLN",
            },
            {
                "id": "ID200",
                "url": "https://www.otomoto.pl/osobowe/oferta/bmw-seria-3-ID200.html",
                "title": "BMW 320i",
                "year_raw": "2019",
            },
            {
                "url": "https://example.com/broken",
                "title": "Broken listing",
            },
        ])
        detail_scraper = _FakeDetailScraper(
            {
                "https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID100.html": {
                    "description": "Detail payload",
                    "year_raw": "2021",
                },
                "https://example.com/broken": {},
            }
        )
        repo = _FakeRepository()
        service = ScrapeService(search_scraper, detail_scraper, repo)

        upserted = service.run({"label": "integration", "brand": "BMW", "model": "Seria 5"}, max_pages=3)

        self.assertEqual(upserted, 2)
        self.assertEqual(
            search_scraper.calls,
            [("https://www.otomoto.pl/osobowe/bmw/seria-5/?search[order]=created_at%3Adesc&search[advanced_search_expanded]=true", 3)],
        )
        self.assertEqual(
            detail_scraper.calls,
            [
                "https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID100.html",
                "https://www.otomoto.pl/osobowe/oferta/bmw-seria-3-ID200.html",
                "https://example.com/broken",
            ],
        )
        self.assertEqual(len(repo.saved), 2)
        self.assertEqual(repo.saved[0].otomoto_id, "ID100")
        self.assertEqual(repo.saved[0].description, "Detail payload")
        self.assertEqual(repo.saved[0].year, 2021)
        self.assertEqual(repo.saved[1].otomoto_id, "ID200")
        self.assertEqual(repo.saved[1].year, 2019)


class ListingPipelineTests(unittest.TestCase):
    def test_skips_detail_fetch_when_disabled(self) -> None:
        detail_scraper = _FakeDetailScraper({"id": "ID123"})
        repo = _FakeRepository()
        pipeline = ListingPipeline(detail_scraper=detail_scraper, repo=repo, skip_detail=True)

        result = pipeline.process({"id": "ID123", "url": "https://example.com/oferta/1"})

        self.assertTrue(result)
        self.assertEqual(detail_scraper.calls, [])
        self.assertEqual(len(repo.saved), 1)

    def test_merges_detail_fields_before_persist(self) -> None:
        detail_scraper = _FakeDetailScraper({
            "description": "Rich detail text",
            "published_at": "2026-03-19T12:34:56Z",
            "photos": ["https://img.example/1.jpg"],
            "source_category": "Osobowe > BMW",
        })
        repo = _FakeRepository()
        pipeline = ListingPipeline(detail_scraper=detail_scraper, repo=repo)

        result = pipeline.process({
            "id": "ID777",
            "url": "https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID777.html",
            "title": "BMW 530d",
            "price_raw": "125 900 PLN",
            "year_raw": "2020",
        })

        self.assertTrue(result)
        self.assertEqual(detail_scraper.calls, ["https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID777.html"])
        self.assertEqual(len(repo.saved), 1)
        saved = repo.saved[0]
        self.assertEqual(saved.otomoto_id, "ID777")
        self.assertEqual(saved.title, "BMW 530d")
        self.assertEqual(saved.description, "Rich detail text")
        self.assertEqual(saved.price_pln, 125900)
        self.assertEqual(saved.year, 2020)
        self.assertEqual(saved.source_category, "Osobowe > BMW")
        self.assertIn("https://img.example/1.jpg", saved.photos_json)
        self.assertIsNotNone(saved.published_at)

    def test_skips_detail_fetch_without_url_and_does_not_persist_invalid_card(self) -> None:
        detail_scraper = _FakeDetailScraper({"description": "Should not be used"})
        repo = _FakeRepository()
        pipeline = ListingPipeline(detail_scraper=detail_scraper, repo=repo)

        result = pipeline.process({"title": "Broken card"})

        self.assertFalse(result)
        self.assertEqual(detail_scraper.calls, [])
        self.assertEqual(repo.saved, [])


class SearchServiceTests(unittest.TestCase):
    def test_runs_multiple_searches_and_keeps_going_after_failure(self) -> None:
        runner = _FakeScrapeRunner(
            {
                "BMW 5 Series": 3,
                "Broken": RuntimeError("boom"),
                "Audi A6": 2,
            }
        )
        service = SearchService(runner)

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "searches.yaml"
            config_path.write_text(
                """
searches:
  bmw_5:
    label: "BMW 5 Series"
  broken_search:
    label: "Broken"
  audi_a6:
    label: "Audi A6"
""".strip(),
                encoding="utf-8",
            )

            result = service.run_all(config_path, max_pages=4)

        self.assertEqual(result, {"bmw_5": 3, "broken_search": 0, "audi_a6": 2})
        self.assertEqual(
            runner.calls,
            [
                ("BMW 5 Series", 4),
                ("Broken", 4),
                ("Audi A6", 4),
            ],
        )

    def test_selects_only_requested_search(self) -> None:
        runner = _FakeScrapeRunner({"BMW 5 Series": 3, "Audi A6": 2})
        service = SearchService(runner)

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "searches.yaml"
            config_path.write_text(
                """
searches:
  bmw_5:
    label: "BMW 5 Series"
  audi_a6:
    label: "Audi A6"
""".strip(),
                encoding="utf-8",
            )

            result = service.run_all(config_path, only="audi_a6", max_pages=2)

        self.assertEqual(result, {"audi_a6": 2})
        self.assertEqual(runner.calls, [("Audi A6", 2)])


class ExportServiceTests(unittest.TestCase):
    def test_exports_csv_and_returns_row_count(self) -> None:
        repo = _FakeExportRepository([
            _make_listing(
                otomoto_id="ID500",
                title="BMW 530d",
                price_pln=125900,
                published_at=datetime(2026, 3, 19, 12, 34, 56, tzinfo=timezone.utc),
                url="https://www.otomoto.pl/osobowe/oferta/bmw-seria-5-ID500.html",
            )
        ])
        service = ExportService(repo)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.csv"
            count = service.export("csv", output_path, filters={"price_max": 130000})

            with output_path.open("r", encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))

        self.assertEqual(count, 1)
        self.assertEqual(repo.calls, [{"price_max": 130000}])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["otomoto_id"], "ID500")
        self.assertEqual(rows[0]["title"], "BMW 530d")
        self.assertEqual(rows[0]["price_pln"], "125900")
        self.assertEqual(rows[0]["published_at"], "2026-03-19T12:34:56+00:00")

    def test_exports_xlsx_and_sets_link_cell(self) -> None:
        repo = _FakeExportRepository([
            _make_listing(
                otomoto_id="ID600",
                title="Audi A6",
                url="https://www.otomoto.pl/osobowe/oferta/audi-a6-ID600.html",
            )
        ])
        service = ExportService(repo)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xlsx"
            count = service.export("xlsx", output_path)
            workbook = load_workbook(output_path)
            sheet = workbook["Listings"]

        self.assertEqual(count, 1)
        self.assertEqual(sheet["A2"].value, "ID600")
        self.assertEqual(sheet["B2"].value, "Audi A6")
        self.assertEqual(sheet["T2"].value, "https://www.otomoto.pl/osobowe/oferta/audi-a6-ID600.html")
        self.assertEqual(sheet["T2"].hyperlink.target, "https://www.otomoto.pl/osobowe/oferta/audi-a6-ID600.html")

    def test_returns_zero_and_skips_file_write_when_no_rows(self) -> None:
        repo = _FakeExportRepository([])
        service = ExportService(repo)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "empty.csv"
            count = service.export("csv", output_path)

        self.assertEqual(count, 0)
        self.assertFalse(output_path.exists())


class QueryEngineTests(unittest.TestCase):
    def test_build_query_applies_requested_sort(self) -> None:
        stmt = QueryEngine().build_query({"sort": "price_asc"})
        compiled = str(stmt)

        self.assertIn("ORDER BY listings.price_pln ASC", compiled)

    def test_build_query_defaults_to_newest_sort(self) -> None:
        stmt = QueryEngine().build_query({})
        compiled = str(stmt)

        self.assertIn("ORDER BY listings.updated_at DESC", compiled)

    def test_build_query_accepts_zero_value_filters(self) -> None:
        stmt = QueryEngine().build_query({"price_max": 0, "year_min": 0, "mileage_max": 0})
        compiled = str(stmt)

        self.assertIn("listings.price_pln <=", compiled)
        self.assertIn("listings.year >=", compiled)
        self.assertIn("listings.mileage_km <=", compiled)


class _FakeSearchScraper:
    def __init__(self, cards: list[dict[str, str]]):
        self._cards = cards
        self.calls: list[tuple[str, Any]] = []

    def scrape_all(self, base_url: str, max_pages=None) -> list[dict[str, str]]:
        self.calls.append((base_url, max_pages))
        return list(self._cards)


class _FakeDetailScraper:
    def __init__(self, result: dict[str, object] | dict[str, dict[str, object]]):
        self._result = result
        self.calls: list[str] = []

    def scrape(self, url: str) -> dict[str, object]:
        self.calls.append(url)
        url_map = self._result.get(url) if isinstance(self._result, dict) else None
        if isinstance(url_map, dict):
            return dict(url_map)
        return dict(self._result)


class _FakeRepository:
    def __init__(self):
        self.saved: list[ListingData] = []

    def upsert(self, data: ListingData) -> ListingData:
        self.saved.append(data)
        return data


class _FakeExportRepository:
    def __init__(self, listings: list[SimpleNamespace]):
        self._listings = listings
        self.calls: list[dict[str, object] | None] = []

    def find_all(self, filters: dict[str, object] | None = None) -> list[SimpleNamespace]:
        self.calls.append(filters)
        return list(self._listings)


class _FakeScrapeRunner:
    def __init__(self, outcomes: dict[str, int | Exception]):
        self._outcomes = outcomes
        self.calls: list[tuple[str, int | None]] = []

    def run(self, config: dict, max_pages: int | None = None) -> int:
        label = str(config.get("label") or "")
        self.calls.append((label, max_pages))
        value = self._outcomes[label]
        if isinstance(value, Exception):
            raise value
        return value


def _make_listing(**overrides: object) -> SimpleNamespace:
    base = {
        "otomoto_id": "",
        "title": "",
        "price_pln": None,
        "year": None,
        "mileage_km": None,
        "fuel_type": "",
        "transmission": "",
        "engine_cc": None,
        "power_hp": None,
        "body_type": "",
        "colour": "",
        "condition": "",
        "seller_type": "",
        "location": "",
        "origin_country": "",
        "published_at": None,
        "source_category": "",
        "raw_attributes_json": "",
        "photos_json": "",
        "url": "",
        "thumbnail_url": "",
        "scraped_at": datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc),
        "description": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _BlockedHttpClient:
    def get(self, url: str, **kwargs: Any):
        raise AntiBotBlockedError(f"blocked: {url}")

    def close(self) -> None:
        return None


class _FakeBrowserClient:
    def __init__(self):
        self.calls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> BeautifulSoup:
        self.calls.append(url)
        return BeautifulSoup("<html></html>", "lxml")

    def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
