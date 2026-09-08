"""Framework-independent efficient-frontier contracts and preference configuration."""

from dataclasses import dataclass
from typing import Literal, Protocol

from app.domain.errors import DomainValidationError
from app.domain.models import PortfolioWeights
from app.domain.optimization import (
    ExpectedReturnSignal,
    OptimizationConstraints,
    OptimizationRequest,
    RiskEstimate,
    SolverDiagnostics,
    _finite_number,
)

ProfileName = Literal["conservative", "moderate", "aggressive"]
PROFILE_NAMES: tuple[ProfileName, ...] = ("conservative", "moderate", "aggressive")


@dataclass(frozen=True, slots=True)
class ProfileConfiguration:
    fractions: tuple[float, float, float] = (0.2, 0.5, 0.8)
    version: str = "frontier-return-fractions-v1"

    def __post_init__(self) -> None:
        if len(self.fractions) != 3:
            raise DomainValidationError("Exactly three profile fractions are required")
        values = tuple(_finite_number(value, "profile fraction") for value in self.fractions)
        if not 0 <= values[0] < values[1] < values[2] <= 1:
            raise DomainValidationError("Profile fractions must be strictly ordered within [0, 1]")
        if not self.version.strip():
            raise DomainValidationError("Profile mapping version must be non-empty")


@dataclass(frozen=True, slots=True)
class FrontierRequest:
    expected_returns: ExpectedReturnSignal
    risk_estimate: RiskEstimate
    constraints: OptimizationConstraints = OptimizationConstraints()
    profiles: ProfileConfiguration = ProfileConfiguration()

    def __post_init__(self) -> None:
        OptimizationRequest(self.expected_returns, self.risk_estimate, 0.0, self.constraints)


@dataclass(frozen=True, slots=True)
class EstimatedMetrics:
    expected_return: float
    variance: float
    volatility: float


@dataclass(frozen=True, slots=True)
class FrontierPoint:
    id: str
    target_return: float
    weights: PortfolioWeights
    metrics: EstimatedMetrics
    solver: SolverDiagnostics


@dataclass(frozen=True, slots=True)
class ProfileReference:
    name: ProfileName
    fraction: float
    target_return: float
    point_id: str


@dataclass(frozen=True, slots=True)
class FrontierResult:
    points: tuple[FrontierPoint, ...]
    profiles: tuple[ProfileReference, ...]
    diagnostics: tuple[str, ...] = ()


class EfficientFrontierGenerator(Protocol):
    def generate(self, request: FrontierRequest) -> FrontierResult: ...
