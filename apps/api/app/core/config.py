"""Runtime metadata for the API process."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.domain.frontier import ProfileConfiguration

API_TITLE = "Portfolio DSS API"
API_DESCRIPTION = "Decision support for understanding and comparing stock portfolios."
API_VERSION = "0.4.0"
SERVICE_NAME: Literal["portfolio-dss-api"] = "portfolio-dss-api"


@dataclass(frozen=True, slots=True)
class Settings:
    cache_path: Path
    provider_timeout_seconds: float = 15.0
    price_cache_ttl_hours: int = 6
    universe_cache_ttl_hours: int = 24
    stale_fallback_days: int = 7
    maximum_consecutive_missing: int = 5
    frontier_profiles: ProfileConfiguration = ProfileConfiguration()


def load_settings() -> Settings:
    repository_root = Path(__file__).resolve().parents[4]
    return Settings(
        cache_path=Path(
            os.getenv("PORTFOLIO_DSS_CACHE_PATH", repository_root / "data" / "market_data.sqlite3")
        ),
        provider_timeout_seconds=float(os.getenv("PORTFOLIO_DSS_PROVIDER_TIMEOUT", "15")),
        price_cache_ttl_hours=int(os.getenv("PORTFOLIO_DSS_PRICE_CACHE_TTL_HOURS", "6")),
        universe_cache_ttl_hours=int(os.getenv("PORTFOLIO_DSS_UNIVERSE_CACHE_TTL_HOURS", "24")),
        stale_fallback_days=int(os.getenv("PORTFOLIO_DSS_STALE_FALLBACK_DAYS", "7")),
        maximum_consecutive_missing=int(os.getenv("PORTFOLIO_DSS_MAX_CONSECUTIVE_MISSING", "5")),
        frontier_profiles=ProfileConfiguration(
            fractions=(
                float(os.getenv("PORTFOLIO_DSS_CONSERVATIVE_FRACTION", "0.2")),
                float(os.getenv("PORTFOLIO_DSS_MODERATE_FRACTION", "0.5")),
                float(os.getenv("PORTFOLIO_DSS_AGGRESSIVE_FRACTION", "0.8")),
            )
        ),
    )
