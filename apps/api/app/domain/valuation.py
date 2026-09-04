"""Portfolio valuation result types."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.market_data import DataProvenance
from app.domain.models import Currency


@dataclass(frozen=True, slots=True)
class ValuationLineItem:
    ticker: str
    quantity: Decimal
    unit_price: Decimal
    market_value: Decimal
    weight: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioValuationSnapshot:
    requested_as_of: date | None
    valued_on: date
    currency: Currency
    positions: tuple[ValuationLineItem, ...]
    total_market_value: Decimal
    universe_as_of: date
    universe_provenance: DataProvenance
    price_provenance: DataProvenance
    snapshot_hash: str
    assumptions: tuple[str, ...]
