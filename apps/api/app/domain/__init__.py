"""Framework-independent financial domain."""

from app.domain.catalog import AssetCatalog, CurrentUniverseProvider, UniverseSnapshot
from app.domain.conventions import (
    DEFAULT_FINANCIAL_CONVENTIONS,
    AlignmentPolicy,
    FinancialConventions,
    MissingDataPolicy,
    PriceField,
    ReturnConvention,
    ReturnFrequency,
)
from app.domain.errors import (
    DomainValidationError,
    ExternalDataUnavailableError,
    MarketDataValidationError,
)
from app.domain.market_data import (
    AssetPriceSeries,
    DataProvenance,
    MarketDataProvider,
    PriceHistory,
    PriceObservation,
)
from app.domain.models import (
    Asset,
    Currency,
    InvestmentUniverse,
    Money,
    Portfolio,
    PortfolioWeights,
    Position,
    TimeHorizon,
    TimeHorizonUnit,
)
from app.domain.universe import (
    SP500_BENCHMARK_ASSET_ID,
    SP500_BENCHMARK_NAME,
    SP500_UNIVERSE_ID,
    MarketUniverseProvider,
)
from app.domain.valuation import PortfolioValuationSnapshot, ValuationLineItem

__all__ = [
    "DEFAULT_FINANCIAL_CONVENTIONS",
    "SP500_BENCHMARK_ASSET_ID",
    "SP500_BENCHMARK_NAME",
    "SP500_UNIVERSE_ID",
    "AlignmentPolicy",
    "AssetCatalog",
    "AssetPriceSeries",
    "Asset",
    "Currency",
    "CurrentUniverseProvider",
    "DataProvenance",
    "DomainValidationError",
    "ExternalDataUnavailableError",
    "FinancialConventions",
    "InvestmentUniverse",
    "MarketUniverseProvider",
    "MarketDataProvider",
    "MarketDataValidationError",
    "MissingDataPolicy",
    "Money",
    "Portfolio",
    "PortfolioWeights",
    "PortfolioValuationSnapshot",
    "Position",
    "PriceField",
    "PriceHistory",
    "PriceObservation",
    "ReturnConvention",
    "ReturnFrequency",
    "TimeHorizon",
    "TimeHorizonUnit",
    "UniverseSnapshot",
    "ValuationLineItem",
]
