"""Framework-independent return estimation, risk estimation, and optimization contracts."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.domain.conventions import MissingDataPolicy, ReturnConvention, ReturnFrequency
from app.domain.errors import DomainValidationError
from app.domain.models import PortfolioWeights

OPTIMIZATION_TOLERANCE = 1e-8


def _finite_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainValidationError(f"{field_name} must be numerical")
    result = float(value)
    if not math.isfinite(result):
        raise DomainValidationError(f"{field_name} must be finite")
    return result


def _validate_asset_ids(asset_ids: tuple[str, ...]) -> None:
    if not asset_ids or any(not asset_id.strip() for asset_id in asset_ids):
        raise DomainValidationError("asset_ids must be non-empty strings")
    if len(set(asset_ids)) != len(asset_ids):
        raise DomainValidationError("asset_ids must not contain duplicates")


def _validate_estimation_metadata(
    *,
    frequency: ReturnFrequency,
    return_convention: ReturnConvention,
    annualization_periods: int,
    estimation_start: date,
    estimation_end: date,
    observations: int,
    estimator_name: str,
) -> None:
    if not isinstance(frequency, ReturnFrequency):
        raise DomainValidationError("frequency must be a ReturnFrequency")
    if not isinstance(return_convention, ReturnConvention):
        raise DomainValidationError("return_convention must be a ReturnConvention")
    if (
        isinstance(annualization_periods, bool)
        or not isinstance(annualization_periods, int)
        or annualization_periods <= 0
    ):
        raise DomainValidationError("annualization_periods must be a positive integer")
    if estimation_start > estimation_end:
        raise DomainValidationError("estimation_start must not follow estimation_end")
    if isinstance(observations, bool) or not isinstance(observations, int) or observations < 2:
        raise DomainValidationError("observations must be an integer of at least two")
    if not estimator_name.strip():
        raise DomainValidationError("estimator_name must be non-empty")


@dataclass(frozen=True, slots=True)
class AlignedReturnSample:
    """Asset returns sharing one explicit observation window and convention."""

    asset_ids: tuple[str, ...]
    observed_on: tuple[date, ...]
    returns: tuple[tuple[float, ...], ...]
    frequency: ReturnFrequency
    return_convention: ReturnConvention
    annualization_periods: int
    missing_data_policy: MissingDataPolicy

    def __post_init__(self) -> None:
        _validate_asset_ids(self.asset_ids)
        if len(self.asset_ids) != len(self.returns):
            raise DomainValidationError("asset_ids and return rows must align")
        if len(self.observed_on) < 2 or any(
            self.observed_on[index] >= self.observed_on[index + 1]
            for index in range(len(self.observed_on) - 1)
        ):
            raise DomainValidationError("return dates must contain at least two ordered dates")
        if any(len(row) != len(self.observed_on) for row in self.returns):
            raise DomainValidationError("return rows must align with observation dates")
        for row in self.returns:
            for value in row:
                _finite_number(value, "return")
        if not isinstance(self.frequency, ReturnFrequency):
            raise DomainValidationError("frequency must be a ReturnFrequency")
        if not isinstance(self.return_convention, ReturnConvention):
            raise DomainValidationError("return_convention must be a ReturnConvention")
        if (
            isinstance(self.annualization_periods, bool)
            or not isinstance(self.annualization_periods, int)
            or self.annualization_periods <= 0
        ):
            raise DomainValidationError("annualization_periods must be a positive integer")
        if not isinstance(self.missing_data_policy, MissingDataPolicy):
            raise DomainValidationError("missing_data_policy must be a MissingDataPolicy")


@dataclass(frozen=True, slots=True)
class ExpectedReturnSignal:
    asset_ids: tuple[str, ...]
    expected_returns: tuple[float, ...]
    frequency: ReturnFrequency
    return_convention: ReturnConvention
    annualization_periods: int
    estimation_start: date
    estimation_end: date
    observations: int
    estimator_name: str
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_asset_ids(self.asset_ids)
        if len(self.asset_ids) != len(self.expected_returns):
            raise DomainValidationError("asset_ids and expected_returns must align")
        for value in self.expected_returns:
            _finite_number(value, "expected return")
        _validate_estimation_metadata(
            frequency=self.frequency,
            return_convention=self.return_convention,
            annualization_periods=self.annualization_periods,
            estimation_start=self.estimation_start,
            estimation_end=self.estimation_end,
            observations=self.observations,
            estimator_name=self.estimator_name,
        )


@dataclass(frozen=True, slots=True)
class RiskEstimate:
    asset_ids: tuple[str, ...]
    covariance_matrix: tuple[tuple[float, ...], ...]
    frequency: ReturnFrequency
    return_convention: ReturnConvention
    annualization_periods: int
    estimation_start: date
    estimation_end: date
    observations: int
    missing_data_policy: MissingDataPolicy
    estimator_name: str
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_asset_ids(self.asset_ids)
        size = len(self.asset_ids)
        if len(self.covariance_matrix) != size or any(
            len(row) != size for row in self.covariance_matrix
        ):
            raise DomainValidationError("covariance matrix dimensions must match asset_ids")
        for row in self.covariance_matrix:
            for value in row:
                _finite_number(value, "covariance")
        for index in range(size):
            if self.covariance_matrix[index][index] < -OPTIMIZATION_TOLERANCE:
                raise DomainValidationError("covariance diagonal must be non-negative")
            for column in range(index + 1, size):
                if not math.isclose(
                    self.covariance_matrix[index][column],
                    self.covariance_matrix[column][index],
                    rel_tol=0.0,
                    abs_tol=OPTIMIZATION_TOLERANCE,
                ):
                    raise DomainValidationError("covariance matrix must be symmetric")
        _validate_estimation_metadata(
            frequency=self.frequency,
            return_convention=self.return_convention,
            annualization_periods=self.annualization_periods,
            estimation_start=self.estimation_start,
            estimation_end=self.estimation_end,
            observations=self.observations,
            estimator_name=self.estimator_name,
        )
        if not isinstance(self.missing_data_policy, MissingDataPolicy):
            raise DomainValidationError("missing_data_policy must be a MissingDataPolicy")


class ExpectedReturnEstimator(Protocol):
    def estimate(self, sample: AlignedReturnSample) -> ExpectedReturnSignal: ...


class RiskEstimator(Protocol):
    def estimate(self, sample: AlignedReturnSample) -> RiskEstimate: ...


class HistoricalMeanEstimator:
    """Annualized arithmetic mean estimator for periodic simple returns."""

    def estimate(self, sample: AlignedReturnSample) -> ExpectedReturnSignal:
        values = tuple(
            statistics.fmean(row) * sample.annualization_periods for row in sample.returns
        )
        return ExpectedReturnSignal(
            asset_ids=sample.asset_ids,
            expected_returns=values,
            frequency=sample.frequency,
            return_convention=sample.return_convention,
            annualization_periods=sample.annualization_periods,
            estimation_start=sample.observed_on[0],
            estimation_end=sample.observed_on[-1],
            observations=len(sample.observed_on),
            estimator_name="historical_arithmetic_mean",
        )


class HistoricalSampleRiskEstimator:
    """Annualized historical sample covariance estimator."""

    def estimate(self, sample: AlignedReturnSample) -> RiskEstimate:
        covariance = tuple(
            tuple(
                statistics.covariance(left, right) * sample.annualization_periods
                for right in sample.returns
            )
            for left in sample.returns
        )
        zero_variance = tuple(
            asset_id
            for row_index, asset_id in enumerate(sample.asset_ids)
            if math.isclose(covariance[row_index][row_index], 0.0, abs_tol=1e-15)
        )
        diagnostics = (
            ("Zero estimated variance: " + ", ".join(zero_variance) + ".",) if zero_variance else ()
        )
        return RiskEstimate(
            asset_ids=sample.asset_ids,
            covariance_matrix=covariance,
            frequency=sample.frequency,
            return_convention=sample.return_convention,
            annualization_periods=sample.annualization_periods,
            estimation_start=sample.observed_on[0],
            estimation_end=sample.observed_on[-1],
            observations=len(sample.observed_on),
            missing_data_policy=sample.missing_data_policy,
            estimator_name="historical_sample_covariance",
            diagnostics=diagnostics,
        )


@dataclass(frozen=True, slots=True)
class OptimizationConstraints:
    max_weight: float | None = None

    def __post_init__(self) -> None:
        if self.max_weight is not None:
            value = _finite_number(self.max_weight, "max_weight")
            if value <= 0.0 or value > 1.0:
                raise DomainValidationError("max_weight must be greater than zero and at most one")


@dataclass(frozen=True, slots=True)
class OptimizationRequest:
    expected_returns: ExpectedReturnSignal
    risk_estimate: RiskEstimate
    risk_aversion: float
    constraints: OptimizationConstraints = OptimizationConstraints()

    def __post_init__(self) -> None:
        risk_aversion = _finite_number(self.risk_aversion, "risk_aversion")
        if risk_aversion < 0.0:
            raise DomainValidationError("risk_aversion must be non-negative")
        signal = self.expected_returns
        risk = self.risk_estimate
        if signal.asset_ids != risk.asset_ids:
            raise DomainValidationError("expected-return and risk asset ordering must match")
        compatible = (
            signal.frequency == risk.frequency
            and signal.return_convention == risk.return_convention
            and signal.annualization_periods == risk.annualization_periods
            and signal.estimation_start == risk.estimation_start
            and signal.estimation_end == risk.estimation_end
            and signal.observations == risk.observations
        )
        if not compatible:
            raise DomainValidationError("expected-return and risk estimates are incompatible")
        cap = self.constraints.max_weight
        if cap is not None and cap * len(signal.asset_ids) < 1.0 - OPTIMIZATION_TOLERANCE:
            raise DomainValidationError("max_weight makes the budget constraint infeasible")


@dataclass(frozen=True, slots=True)
class PortfolioMetrics:
    expected_return: float
    variance: float
    volatility: float
    objective_value: float


def evaluate_portfolio(
    weights: PortfolioWeights,
    expected_returns: ExpectedReturnSignal,
    risk_estimate: RiskEstimate,
    risk_aversion: float,
) -> PortfolioMetrics:
    if (
        weights.asset_ids != expected_returns.asset_ids
        or weights.asset_ids != risk_estimate.asset_ids
    ):
        raise DomainValidationError("portfolio and model asset ordering must match")
    expected_return = math.fsum(
        weight * value
        for weight, value in zip(weights.weights, expected_returns.expected_returns, strict=True)
    )
    variance = math.fsum(
        weights.weights[row]
        * risk_estimate.covariance_matrix[row][column]
        * weights.weights[column]
        for row in range(len(weights.weights))
        for column in range(len(weights.weights))
    )
    if variance < -OPTIMIZATION_TOLERANCE:
        raise DomainValidationError("portfolio variance must be non-negative")
    variance = max(0.0, variance)
    return PortfolioMetrics(
        expected_return=expected_return,
        variance=variance,
        volatility=math.sqrt(variance),
        objective_value=expected_return - risk_aversion * variance,
    )


@dataclass(frozen=True, slots=True)
class SolverDiagnostics:
    solver_name: str
    success: bool
    status_code: int
    message: str
    iterations: int
    budget_residual: float
    minimum_weight: float
    max_weight_violation: float
    binding_asset_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    weights: PortfolioWeights
    metrics: PortfolioMetrics
    constraint_status: str
    solver: SolverDiagnostics

    def __post_init__(self) -> None:
        if not self.solver.success or self.constraint_status != "valid":
            raise DomainValidationError("an optimization result must be valid and successful")


class PortfolioOptimizer(Protocol):
    def optimize(self, request: OptimizationRequest) -> OptimizationResult: ...
