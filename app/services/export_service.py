"""Otomoto Parser – Export service (dispatches to CSV / XLSX exporters)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Protocol

from app.exporters.csv_exporter import CsvExporter
from app.exporters.xlsx_exporter import XlsxExporter

logger = logging.getLogger(__name__)


class ListingReaderLike(Protocol):
    def find_all(self, filters: Optional[dict] = None) -> list:
        ...


class ExportService:
    """Queries the DB and writes results to CSV or XLSX."""

    def __init__(self, repo: ListingReaderLike) -> None:
        self._repo = repo
        self._csv = CsvExporter()
        self._xlsx = XlsxExporter()

    def export(
        self,
        fmt: str,
        output_path: Path,
        filters: Optional[dict] = None,
    ) -> int:
        """Export listings matching *filters* to *output_path*.

        Args:
            fmt: 'csv' or 'xlsx'
            output_path: Destination file path.
            filters: Optional filter dict (see ListingRepository.find_all).

        Returns:
            Number of listings exported.
        """
        listings = self._repo.find_all(filters=filters)
        if not listings:
            logger.warning("No listings match the given filters, export skipped")
            return 0

        fmt = fmt.lower().strip()
        if fmt == "csv":
            self._csv.export(listings, output_path)
        elif fmt in ("xlsx", "excel"):
            self._xlsx.export(listings, output_path)
        else:
            raise ValueError(f"Unsupported export format: {fmt!r}. Use 'csv' or 'xlsx'.")

        logger.info(f"Exported {len(listings)} listings to {output_path} ({fmt})")
        return len(listings)
