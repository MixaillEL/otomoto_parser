# Otomoto Parser

A production-ready Python scraper for [otomoto.pl](https://www.otomoto.pl), focused on configurable search collection, normalized vehicle data, SQLite storage, and export workflows for analysis.

## Highlights

- Configurable search URL generation from structured filters
- Search-result pagination and detail-page scraping
- Normalized listing data stored in SQLite via SQLAlchemy
- Local database search from the CLI
- CSV and XLSX export
- Deduplication by listing identity and canonical URL
- Retry with backoff, user-agent rotation, anti-bot handling
- Optional Playwright fallback when HTTP scraping is blocked

## What The Project Stores

Each listing can include:

- Core fields: title, price, year, mileage, fuel type, transmission, engine size, power
- Seller and vehicle metadata: body type, condition, colour, seller type, location, origin country
- Content fields: description, thumbnail, published time, source category
- Extended raw data: photo list and raw attribute JSON

## Quick Start

### 1. Create a virtual environment

```bash
cd "c:\My Project\otomoto_parser"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure the project

```bash
copy config\.env.example config\.env
```

Then edit:

- `config/searches.yaml` to define saved searches
- `config/.env` to adjust runtime settings

### 3. Run the scraper

```bash
python -m app.main scrape
python -m app.main scrape --search bmw_5
python -m app.main scrape --max-pages 2
python -m app.main scrape --skip-detail
```

## CLI Commands

### Scrape configured searches

```bash
python -m app.main scrape
python -m app.main scrape --search bmw_5
python -m app.main scrape --max-pages 3
python -m app.main scrape --skip-detail
```

### Show database stats

```bash
python -m app.main stats
```

### Search the local SQLite database

```bash
python -m app.main search --price-max 100000 --year-min 2018
python -m app.main search --fuel-type diesel --body-type suv --limit 10
python -m app.main search --sort price_asc --limit 25
```

### Export results

```bash
python -m app.main export --fmt csv --output exports/results.csv
python -m app.main export --fmt xlsx --price-max 100000 --year-min 2018
python -m app.main export --fmt csv --sort year_desc --output exports/newest-cars.csv
```

## Search Configuration

Example `config/searches.yaml`:

```yaml
searches:
  my_search:
    label: "BMW 5 Series"
    brand: BMW
    model: "Seria 5"
    year_from: 2018
    year_to: 2023
    price_to: 150000
    fuel_type: petrol
    transmission: automatic
    sort: price_asc
    max_pages: 5
```

Supported URL-building inputs include:

- `brand`, `model`, `body_type`
- `year_from`, `year_to`
- `price_from`, `price_to`
- `mileage_max`
- `fuel_type`, `transmission`
- `sort`, `max_pages`

## Environment Variables

Key values from `config/.env`:

| Variable | Default | Purpose |
|---|---|---|
| `DB_PATH` | `data/otomoto.db` | SQLite database file |
| `LOG_LEVEL` | `INFO` | Logging level |
| `REQUEST_DELAY_MS` | `1500` | Base delay between requests |
| `REQUEST_JITTER_RATIO` | `0.3` | Randomized delay multiplier |
| `HTTP_TIMEOUT_S` | `20.0` | Base HTTP timeout |
| `MAX_PAGES` | empty | Global page limit override |
| `RETRY_ATTEMPTS` | `3` | Retry attempts for fetches |
| `RETRY_BASE_DELAY_S` | `2.0` | Base retry delay |
| `EXPORT_DIR` | `exports` | Default export directory |
| `USE_BROWSER` | `false` | Force browser mode |
| `BROWSER_FALLBACK_ON_BLOCK` | `true` | Switch to Playwright on block detection |
| `BROWSER_TYPE` | `chromium` | Browser engine |

## Optional Playwright Setup

If the site requires JavaScript rendering or blocks plain HTTP requests:

```bash
pip install playwright
playwright install chromium
```

Then enable browser support in `config/.env`:

```env
USE_BROWSER=true
```

Or leave `USE_BROWSER=false` and rely on:

```env
BROWSER_FALLBACK_ON_BLOCK=true
```

## Project Structure

```text
otomoto_parser/
├── app/
│   ├── main.py
│   ├── logger.py
│   ├── clients/
│   ├── core/
│   ├── exporters/
│   ├── filters/
│   ├── scrapers/
│   ├── services/
│   └── storage/
├── config/
│   ├── .env.example
│   └── searches.yaml
├── tests/
├── .github/workflows/
├── requirements.txt
└── README.md
```

## Development

Run tests:

```bash
python -m unittest discover -s tests -v
```

Run a quick syntax check:

```bash
python -m py_compile app/main.py
```

GitHub Actions CI is configured in `.github/workflows/ci.yml`.

## Publishing Notes

Before publishing to GitHub:

- keep `config/.env` local only
- do not commit `data/`, `logs/`, `exports/`, or `.venv/`
- review `config/searches.yaml` for sample-only content
- choose and add a project license if you want public reuse rights

## Help

```bash
python -m app.main --help
python -m app.main scrape --help
python -m app.main search --help
python -m app.main export --help
python -m app.main stats --help
```
