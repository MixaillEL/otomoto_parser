# Release Notes

## v1.0.0

Initial public release of `otomoto_parser`.

### Included

- Configurable Otomoto search scraping from YAML
- Search-result pagination
- Detail-page scraping with normalized listing fields
- SQLite persistence via SQLAlchemy
- Local CLI database search
- CSV and XLSX export
- Deduplication by listing identity and canonical URL
- Database indexes and lightweight schema bootstrap for existing SQLite files
- Retry with backoff and jitter
- User-Agent rotation and anti-bot response handling
- Optional Playwright fallback when blocked
- Rotating log files and CLI-friendly console logging
- Basic regression tests and GitHub Actions CI

### Notes

- `config/.env` is intentionally excluded from git
- runtime artifacts such as `data/`, `logs/`, and `exports/` are gitignored
- Playwright is optional and only needed for browser-mode scraping
