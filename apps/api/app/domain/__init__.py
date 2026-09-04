"""Framework-independent financial domain."""

from app.domain.analysis import (
    AnalysisValuation,
    AnalysisValuationPosition,
    AnalysisWindow,
    PortfolioAnalysisReport,
)
from app.domain.analytics import (
    ConcentrationComponent,
    ConcentrationSummary,
    HistoricalAnalytics,
    HistoricalSeriesPoint,
    LabelledMatrix,
    PerformanceSummary,
    calculate_historical_analytics,
    concentration,
)
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
    "AnalysisValuation",
    "AnalysisValuationPosition",
    "AnalysisWindow",
    "AssetCatalog",
    "AssetPriceSeries",
    "Asset",
    "Currency",
    "ConcentrationComponent",
    "ConcentrationSummary",
    "CurrentUniverseProvider",
    "DataProvenance",
    "DomainValidationError",
    "ExternalDataUnavailableError",
    "FinancialConventions",
    "HistoricalAnalytics",
    "HistoricalSeriesPoint",
    "InvestmentUniverse",
    "LabelledMatrix",
    "MarketUniverseProvider",
    "MarketDataProvider",
    "MarketDataValidationError",
    "MissingDataPolicy",
    "Money",
    "Portfolio",
    "PortfolioAnalysisReport",
    "PortfolioWeights",
    "PortfolioValuationSnapshot",
    "Position",
    "PriceField",
    "PriceHistory",
    "PriceObservation",
    "PerformanceSummary",
    "ReturnConvention",
    "ReturnFrequency",
    "TimeHorizon",
    "TimeHorizonUnit",
    "UniverseSnapshot",
    "ValuationLineItem",
    "calculate_historical_analytics",
    "concentration",
]
