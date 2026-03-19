"""Otomoto Parser – Logging setup."""
from __future__ import annotations

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger: Rich console handler + rotating file handler."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Ensure logs directory exists
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    if logging.getLogger().handlers:
        logging.getLogger().setLevel(log_level)
        return

    handlers: list[logging.Handler] = [
        RichHandler(
            level=log_level,
            rich_tracebacks=True,
            show_path=False,
            markup=True,
        ),
        RotatingFileHandler(
            log_file,
            encoding="utf-8",
            maxBytes=2_000_000,
            backupCount=3,
        ),
    ]

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=False,
    )

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "charset_normalizer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
