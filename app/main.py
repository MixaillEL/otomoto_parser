"""Otomoto Parser – Typer CLI entry point."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

# Ensure project root is on sys.path when run as `python app/main.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.logger import setup_logging
from app.core.settings import settings

app = typer.Typer(
    name="otomoto-parser",
    help="[bold]Otomoto.pl car listing scraper[/bold]",
    rich_markup_mode="rich",
    add_completion=False,
)

console = Console()

# Paths
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SEARCHES_YAML = _PROJECT_ROOT / "config" / "searches.yaml"


# ---------------------------------------------------------------------------
# scrape
# ---------------------------------------------------------------------------

@app.command()
def scrape(
    search: Optional[str] = typer.Option(
        None, "--search", "-s",
        help="Run only the named search (as defined in searches.yaml). "
             "Omit to run all searches.",
    ),
    max_pages: Optional[int] = typer.Option(
        None, "--max-pages", "-p",
        help="Max pages per search (overrides per-search and global settings).",
    ),
    skip_detail: bool = typer.Option(
        False, "--skip-detail",
        help="Only scrape search result cards; skip individual detail pages.",
    ),
    config: Path = typer.Option(
        _SEARCHES_YAML, "--config", "-c",
        help="Path to searches.yaml config file.",
    ),
) -> None:
    """Scrape otomoto.pl listings and save to the database."""
    _init()

    from app.clients.resilient_client import ResilientOtomotoClient
    from app.scrapers.search_scraper import SearchScraper
    from app.scrapers.detail_scraper import DetailScraper
    from app.services.scrape_service import ScrapeService
    from app.services.search_service import SearchService
    from app.storage.repository import ListingRepository

    client = ResilientOtomotoClient()

    try:
        search_scraper = SearchScraper(client)
        detail_scraper = DetailScraper(client)
        repo = ListingRepository()

        scrape_svc = ScrapeService(
            search_scraper, detail_scraper, repo,
            skip_detail=skip_detail,
        )
        search_svc = SearchService(scrape_svc)

        rprint("\n[bold cyan]Otomoto Parser[/bold cyan] - starting scrape\n")
        results = search_svc.run_all(
            config_path=config,
            only=search,
            max_pages=max_pages,
        )

        total = sum(results.values())
        _print_scrape_summary(results)
        rprint(f"\n[bold green]Done![/bold green] {total} listings saved to database.\n")

    finally:
        client.close()


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

@app.command()
def export(
    fmt: str = typer.Option(
        "csv", "--fmt", "-f",
        help="Export format: csv or xlsx.",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file path. Defaults to exports/otomoto.<fmt>.",
    ),
    price_min: Optional[int] = typer.Option(None, help="Filter: minimum price (PLN)"),
    price_max: Optional[int] = typer.Option(None, help="Filter: maximum price (PLN)"),
    year_min: Optional[int] = typer.Option(None, help="Filter: minimum year"),
    year_max: Optional[int] = typer.Option(None, help="Filter: maximum year"),
    mileage_max: Optional[int] = typer.Option(None, help="Filter: max mileage (km)"),
    fuel_type: Optional[str] = typer.Option(None, help="Filter: fuel type (petrol/diesel/hybrid/electric)"),
    transmission: Optional[str] = typer.Option(None, help="Filter: transmission (manual/automatic)"),
    seller_type: Optional[str] = typer.Option(None, help="Filter: seller_type (private/dealer)"),
    body_type: Optional[str] = typer.Option(None, help="Filter: body type (sedan/suv/compact/combi/...)"),
    colour: Optional[str] = typer.Option(None, help="Filter: colour substring match"),
    condition: Optional[str] = typer.Option(None, help="Filter: condition"),
    location: Optional[str] = typer.Option(None, help="Filter: location substring match"),
    sort: str = typer.Option(
        "newest",
        help="Sort order: newest, oldest, price_asc, price_desc, year_desc, year_asc, mileage_asc, mileage_desc.",
    ),
) -> None:
    """Export listings from the database to CSV or XLSX."""
    _init()

    from app.services.export_service import ExportService
    from app.storage.repository import ListingRepository

    default_name = f"otomoto.{fmt.lower()}"
    out_path = output or (settings.export_path / default_name)

    filters = _build_listing_filters(
        price_min=price_min,
        price_max=price_max,
        year_min=year_min,
        year_max=year_max,
        mileage_max=mileage_max,
        fuel_type=fuel_type,
        transmission=transmission,
        seller_type=seller_type,
        body_type=body_type,
        colour=colour,
        condition=condition,
        location=location,
        sort=sort,
    )

    repo = ListingRepository()
    svc = ExportService(repo)

    rprint(f"\n[bold cyan]Exporting to {fmt.upper()}...[/bold cyan]")
    count = svc.export(fmt=fmt, output_path=Path(out_path), filters=filters or None)

    if count:
        rprint(f"[bold green]{count} listings exported -> {out_path}[/bold green]\n")
    else:
        rprint("[yellow]No listings matched the filters.[/yellow]\n")


@app.command()
def search(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of listings to show."),
    price_min: Optional[int] = typer.Option(None, help="Filter: minimum price (PLN)"),
    price_max: Optional[int] = typer.Option(None, help="Filter: maximum price (PLN)"),
    year_min: Optional[int] = typer.Option(None, help="Filter: minimum year"),
    year_max: Optional[int] = typer.Option(None, help="Filter: maximum year"),
    mileage_max: Optional[int] = typer.Option(None, help="Filter: max mileage (km)"),
    fuel_type: Optional[str] = typer.Option(None, help="Filter: fuel type (petrol/diesel/hybrid/electric)"),
    transmission: Optional[str] = typer.Option(None, help="Filter: transmission (manual/automatic)"),
    seller_type: Optional[str] = typer.Option(None, help="Filter: seller_type (private/dealer)"),
    body_type: Optional[str] = typer.Option(None, help="Filter: body type (sedan/suv/compact/combi/...)"),
    colour: Optional[str] = typer.Option(None, help="Filter: colour substring match"),
    condition: Optional[str] = typer.Option(None, help="Filter: condition"),
    location: Optional[str] = typer.Option(None, help="Filter: location substring match"),
    sort: str = typer.Option(
        "newest",
        help="Sort order: newest, oldest, price_asc, price_desc, year_desc, year_asc, mileage_asc, mileage_desc.",
    ),
) -> None:
    """Search listings in the local SQLite database."""
    _init()

    from app.storage.repository import ListingRepository

    filters = _build_listing_filters(
        price_min=price_min,
        price_max=price_max,
        year_min=year_min,
        year_max=year_max,
        mileage_max=mileage_max,
        fuel_type=fuel_type,
        transmission=transmission,
        seller_type=seller_type,
        body_type=body_type,
        colour=colour,
        condition=condition,
        location=location,
        sort=sort,
    )

    repo = ListingRepository()
    listings = repo.find_all(filters=filters or None, limit=max(limit, 1))

    if not listings:
        rprint("[yellow]No listings matched the filters.[/yellow]\n")
        return

    tbl = Table(show_header=True, header_style="bold blue", title="Search Results")
    tbl.add_column("ID", style="cyan")
    tbl.add_column("Title")
    tbl.add_column("Price", justify="right")
    tbl.add_column("Year", justify="right")
    tbl.add_column("Mileage", justify="right")
    tbl.add_column("Fuel")
    tbl.add_column("Location")

    for listing in listings:
        tbl.add_row(
            listing.otomoto_id,
            listing.title,
            f"{listing.price_pln:,}" if listing.price_pln else "–",
            str(listing.year or "–"),
            f"{listing.mileage_km:,}" if listing.mileage_km else "–",
            listing.fuel_type or "–",
            listing.location or "–",
        )

    console.print(tbl)
    rprint(f"\n[bold green]{len(listings)} listings shown.[/bold green]\n")


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

@app.command()
def stats() -> None:
    """Show database statistics."""
    _init()

    from app.storage.repository import ListingRepository
    from app.storage.db import get_session
    from sqlalchemy import func, select
    from app.storage.models import Listing

    repo = ListingRepository()
    total = repo.count()

    rprint("\n[bold cyan]Otomoto Parser - Database Stats[/bold cyan]\n")

    tbl = Table(show_header=True, header_style="bold blue")
    tbl.add_column("Metric", style="dim")
    tbl.add_column("Value", justify="right")

    tbl.add_row("Total listings", str(total))
    tbl.add_row("DB path", str(Path(settings.db_path).resolve()))

    if total > 0:
        with get_session() as session:
            min_price = session.scalar(select(func.min(Listing.price_pln)))
            max_price = session.scalar(select(func.max(Listing.price_pln)))
            avg_price = session.scalar(select(func.avg(Listing.price_pln)))
            avg_year  = session.scalar(select(func.avg(Listing.year)))

        tbl.add_row("Price min (PLN)", f"{min_price:,}" if min_price else "–")
        tbl.add_row("Price max (PLN)", f"{max_price:,}" if max_price else "–")
        tbl.add_row("Price avg (PLN)", f"{int(avg_price):,}" if avg_price else "–")
        tbl.add_row("Year avg", f"{int(avg_year)}" if avg_year else "–")

    console.print(tbl)
    rprint()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init() -> None:
    """Bootstrap logging and DB."""
    setup_logging(settings.log_level)

    from app.storage.db import init_db
    init_db(settings.db_url)


def _print_scrape_summary(results: dict[str, int]) -> None:
    tbl = Table(show_header=True, header_style="bold blue", title="Scrape Results")
    tbl.add_column("Search", style="cyan")
    tbl.add_column("Listings upserted", justify="right")
    for name, count in results.items():
        tbl.add_row(name, str(count))
    console.print(tbl)


def _build_listing_filters(**kwargs) -> dict[str, object]:
    return {key: value for key, value in kwargs.items() if value is not None}


if __name__ == "__main__":
    app()
