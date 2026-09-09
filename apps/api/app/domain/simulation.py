"""Framework-independent contracts for marginal portfolio outcome distributions."""

import math
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class SimulationConfiguration:
    horizon_years: int = 1
    paths: int = 10000
    seed: int = 42

    def __post_init__(self) -> None:
        if any(type(v) is not int for v in (self.horizon_years, self.paths, self.seed)):
            raise DomainValidationError("Simulation settings must be integers")
        if self.horizon_years not in (1, 3, 5) or self.paths not in (1000, 10000, 50000):
            raise DomainValidationError("Unsupported horizon or path count")
        if not 0 <= self.seed <= 2**32 - 1:
            raise DomainValidationError("Seed must be an unsigned 32-bit integer")


@dataclass(frozen=True, slots=True)
class SimulationMetadata:
    estimation_start: date
    estimation_end: date
    observations: int
    return_estimator: str
    risk_estimator: str
    currency: str = "USD"
    price_field: str = "adjusted_close"
    return_convention: str = "simple"
    frequency: str = "daily"
    annualization_periods: int = 252

    def __post_init__(self) -> None:
        if self.estimation_start >= self.estimation_end or self.observations < 2:
            raise DomainValidationError("Invalid estimation window")
        if not self.return_estimator.strip() or not self.risk_estimator.strip():
            raise DomainValidationError("Estimator identities are required")
        if (
            self.currency,
            self.price_field,
            self.return_convention,
            self.frequency,
            self.annualization_periods,
        ) != ("USD", "adjusted_close", "simple", "daily", 252):
            raise DomainValidationError("Unsupported simulation conventions")


@dataclass(frozen=True, slots=True)
class SimulationPortfolio:
    id: str
    annual_mean: float
    annual_variance: float
    metadata: SimulationMetadata

    def __post_init__(self) -> None:
        if not self.id.strip() or len(self.id) > 80:
            raise DomainValidationError("A short portfolio ID is required")
        if (
            any(
                isinstance(v, bool) or not math.isfinite(v)
                for v in (self.annual_mean, self.annual_variance)
            )
            or self.annual_variance < 0
        ):
            raise DomainValidationError("Mean must be finite and variance finite and nonnegative")


@dataclass(frozen=True, slots=True)
class SimulationRequest:
    portfolios: tuple[SimulationPortfolio, ...]
    initial_capital: float
    source_report_hash: str
    configuration: SimulationConfiguration = SimulationConfiguration()

    def __post_init__(self) -> None:
        if not 1 <= len(self.portfolios) <= 6:
            raise DomainValidationError("Provide between one and six portfolios")
        if len({p.id for p in self.portfolios}) != len(self.portfolios):
            raise DomainValidationError("Portfolio IDs must be unique")
        if (
            isinstance(self.initial_capital, bool)
            or not math.isfinite(self.initial_capital)
            or self.initial_capital <= 0
        ):
            raise DomainValidationError("Initial capital must be finite and positive")
        if len(self.source_report_hash) != 64 or any(
            c not in "0123456789abcdef" for c in self.source_report_hash
        ):
            raise DomainValidationError("Source report hash must be a SHA-256 hex digest")
        first = self.portfolios[0].metadata
        for portfolio in self.portfolios:
            m = portfolio.metadata
            if (m.estimation_start, m.estimation_end, m.observations) != (
                first.estimation_start,
                first.estimation_end,
                first.observations,
            ):
                raise DomainValidationError("All portfolios must share estimation observations")


@dataclass(frozen=True, slots=True)
class DistributionMetrics:
    mean: float
    standard_deviation: float
    percentiles: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class FanPoint:
    month: int
    percentiles: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PortfolioSimulation:
    id: str
    terminal_value: DistributionMetrics
    terminal_return: DistributionMetrics
    probability_of_loss: float
    fan: tuple[FanPoint, ...]
    histogram_counts: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SimulationAssumptions:
    model_version: str = "constant-weight-lognormal-v1"
    rng_version: str = "PCG64-parameter-substreams-v1"
    percentile_levels: tuple[int, ...] = (5, 25, 50, 75, 95)
    observation_interval_years: float = 1 / 12
    statements: tuple[str, ...] = (
        "Simulated outcomes are not forecasts or guaranteed future values.",
        "Weights are continuously maintained, including current holdings; parameters are constant.",
        "Annualized daily arithmetic estimates approximate continuous-time diffusion parameters.",
        "Nominal USD with reinvested dividends; no contributions, withdrawals, "
        "fees, taxes or inflation.",
        "Bands describe pointwise outcome percentiles, not paths or "
        "parameter-estimation uncertainty.",
        "Marginal distributions only; no jointly modeled market scenarios "
        "or outperformance probability.",
        "Submitted estimates are scenario inputs; the source hash is provenance, "
        "not authentication.",
        "Replay requires identical inputs and numerical environment; "
        "a seed alone does not freeze data.",
    )


@dataclass(frozen=True, slots=True)
class SimulationResult:
    scenario: SimulationRequest
    assumptions: SimulationAssumptions
    numerical_environment: str
    portfolios: tuple[PortfolioSimulation, ...]
    histogram_edges: tuple[float, ...]
    input_fingerprint: str
    result_hash: str


class SimulationEngine(Protocol):
    def simulate(self, request: SimulationRequest) -> SimulationResult: ...


class SimulationNumericalError(Exception):
    """The requested distribution cannot be represented safely with finite floats."""
