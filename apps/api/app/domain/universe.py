"""Investment-universe contracts and stable identifiers."""

from datetime import date
from typing import Protocol

from app.domain.models import InvestmentUniverse

SP500_UNIVERSE_ID = "sp500"
SP500_BENCHMARK_ASSET_ID = "SPY"
SP500_BENCHMARK_NAME = "SPDR S&P 500 ETF Trust (total-return proxy)"


class MarketUniverseProvider(Protocol):
    """Port for retrieving a dated investment universe."""

    def get_universe(self, universe_id: str, as_of: date) -> InvestmentUniverse:
        """Return the requested universe as it was defined on the given date."""
        ...
