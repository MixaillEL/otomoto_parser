"""Otomoto Parser – Application settings (pydantic-settings)."""
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve .env path relative to project root.
_ENV_FILE = Path(__file__).resolve().parents[2] / "config" / ".env"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    db_path: str = "data/otomoto.db"

    # Logging
    log_level: str = "INFO"

    # HTTP behaviour
    request_delay_ms: int = 1500
    request_jitter_ratio: float = 0.3
    http_timeout_s: float = 20.0
    user_agent: Optional[str] = None
    retry_attempts: int = 3
    retry_base_delay_s: float = 2.0

    # Scraping limits
    max_pages: Optional[int] = None  # global override; per-search value used if None

    # Exports
    export_dir: str = "exports"

    # Browser fallback
    use_browser: bool = False
    browser_fallback_on_block: bool = True
    browser_type: str = "chromium"

    @property
    def db_url(self) -> str:
        """SQLAlchemy connection string."""
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.resolve()}"

    @property
    def export_path(self) -> Path:
        p = Path(self.export_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


# Singleton – import this in all modules
settings = AppSettings()
