"""Application-facing historical analysis report values."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.analytics import HistoricalAnalytics
from app.domain.market_data import DataProvenance
from app.domain.models import Currency


@dataclass(frozen=True, slots=True)
class AnalysisValuationPosition:
    ticker: str
    quantity: Decimal
    unit_price: Decimal
    market_value: Decimal
    weight: Decimal
    sector: str


@dataclass(frozen=True, slots=True)
class AnalysisValuation:
    valued_on: date
    currency: Currency
    total_market_value: Decimal
    positions: tuple[AnalysisValuationPosition, ...]


@dataclass(frozen=True, slots=True)
class AnalysisWindow:
    requested_start: date
    requested_end: date
    effective_start: date
    effective_end: date
    aligned_price_observations: int
    return_observations: int
    excluded_observations: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class PortfolioAnalysisReport:
    valuation: AnalysisValuation
    window: AnalysisWindow
    analytics: HistoricalAnalytics
    universe_as_of: date
    universe_provenance: DataProvenance
    price_provenance: DataProvenance
    assumptions: tuple[str, ...]
    diagnostics: tuple[str, ...]
    analysis_hash: str
