"""Framework-independent financial domain."""

from app.domain.conventions import (
    DEFAULT_FINANCIAL_CONVENTIONS,
    AlignmentPolicy,
    FinancialConventions,
    MissingDataPolicy,
    PriceField,
    ReturnConvention,
    ReturnFrequency,
)
from app.domain.errors import DomainValidationError
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

__all__ = [
    "DEFAULT_FINANCIAL_CONVENTIONS",
    "SP500_BENCHMARK_ASSET_ID",
    "SP500_BENCHMARK_NAME",
    "SP500_UNIVERSE_ID",
    "AlignmentPolicy",
    "Asset",
    "Currency",
    "DomainValidationError",
    "FinancialConventions",
    "InvestmentUniverse",
    "MarketUniverseProvider",
    "MissingDataPolicy",
    "Money",
    "Portfolio",
    "PortfolioWeights",
    "Position",
    "PriceField",
    "ReturnConvention",
    "ReturnFrequency",
    "TimeHorizon",
    "TimeHorizonUnit",
]
