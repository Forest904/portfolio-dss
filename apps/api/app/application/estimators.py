"""Versioned estimator composition and fixed-weight comparisons, outside solvers."""

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.application.errors import invalid_input
from app.domain.errors import DomainValidationError
from app.domain.forecast import HALF_LIFE, SimpleForecastEstimator, exponential_weights
from app.domain.models import PortfolioWeights
from app.domain.optimization import (
    AlignedReturnSample,
    ExpectedReturnEstimator,
    ExpectedReturnSignal,
)

EstimatorId = Literal["historical_mean", "simple_forecast"]
COMPARISON_VERSION = "expected-return-comparison-v1"
HISTORICAL_VERSION = "historical-arithmetic-mean-v1"
FORECAST_VERSION = "normalized-exponential-mean-v1"
BUILTIN_CONFIGURATION = (
    f"{COMPARISON_VERSION}:{HISTORICAL_VERSION}:{FORECAST_VERSION}:half-life={HALF_LIFE}"
)


@dataclass(frozen=True, slots=True)
class EstimatorMetadata:
    model_id: EstimatorId
    version: str
    weighting_method: str
    half_life_observations: int | None
    effective_sample_size: float
    latest_observation_weight: float
    estimation_start: date
    estimation_end: date
    observations: int


@dataclass(frozen=True, slots=True)
class ComparedModel:
    signal: ExpectedReturnSignal
    metadata: EstimatorMetadata


@dataclass(frozen=True, slots=True)
class ModelPair:
    historical: ComparedModel
    forecast: ComparedModel

    def selected(self, model_id: EstimatorId) -> ExpectedReturnSignal:
        return {"historical_mean": self.historical, "simple_forecast": self.forecast}[
            model_id
        ].signal


@dataclass(frozen=True, slots=True)
class PortfolioReturnComparison:
    id: str
    historical_expected_return: float
    forecast_expected_return: float
    difference: float

    def __post_init__(self) -> None:
        if not all(
            math.isfinite(v)
            for v in (
                self.historical_expected_return,
                self.forecast_expected_return,
                self.difference,
            )
        ):
            raise invalid_input(
                "ESTIMATION_NUMERICAL_FAILURE", "Expected-return comparison is not finite."
            )


@dataclass(frozen=True, slots=True)
class ExpectedReturnComparison:
    selected_estimator: EstimatorId
    assets: ModelPair
    benchmark: ModelPair | None
    portfolios: tuple[PortfolioReturnComparison, ...]
    version: str = COMPARISON_VERSION


class EstimatorRegistry:
    def __init__(
        self,
        historical: ExpectedReturnEstimator,
        forecast: ExpectedReturnEstimator | None = None,
        *,
        historical_version: str = HISTORICAL_VERSION,
        forecast_version: str = FORECAST_VERSION,
    ) -> None:
        self._versions = {
            "historical_mean": historical_version,
            "simple_forecast": forecast_version,
        }
        self._models: dict[EstimatorId, ExpectedReturnEstimator] = {
            "historical_mean": historical,
            "simple_forecast": forecast or SimpleForecastEstimator(),
        }

    def identity(self, model_id: EstimatorId) -> str:
        model = self._models[model_id]
        return (
            f"{COMPARISON_VERSION}:{model_id}:{self._versions[model_id]}:"
            f"half-life={HALF_LIFE if model_id == 'simple_forecast' else 'none'}:"
            f"{type(model).__module__}.{type(model).__qualname__}"
        )

    def estimate(self, sample: AlignedReturnSample) -> ModelPair:
        def run(model_id: EstimatorId) -> ComparedModel:
            try:
                signal = self._models[model_id].estimate(sample)
            except (DomainValidationError, OverflowError) as exc:
                raise invalid_input(
                    "ESTIMATION_NUMERICAL_FAILURE",
                    "The selected sample cannot produce valid finite estimates.",
                ) from exc
            n = len(sample.observed_on)
            weights = exponential_weights(n) if model_id == "simple_forecast" else (1 / n,) * n
            return ComparedModel(
                signal,
                EstimatorMetadata(
                    model_id,
                    self.identity(model_id),
                    "normalized_exponential" if model_id == "simple_forecast" else "uniform",
                    HALF_LIFE if model_id == "simple_forecast" else None,
                    1 / math.fsum(w * w for w in weights),
                    weights[-1],
                    signal.estimation_start,
                    signal.estimation_end,
                    n,
                ),
            )

        return ModelPair(run("historical_mean"), run("simple_forecast"))


def compare_weights(
    name: str, weights: PortfolioWeights, pair: ModelPair
) -> PortfolioReturnComparison:
    def mean(signal: ExpectedReturnSignal) -> float:
        if weights.asset_ids != signal.asset_ids:
            raise ValueError("Comparison assets must match signal ordering")
        return math.fsum(
            w * r for w, r in zip(weights.weights, signal.expected_returns, strict=True)
        )

    historical, forecast = mean(pair.historical.signal), mean(pair.forecast.signal)
    return PortfolioReturnComparison(name, historical, forecast, forecast - historical)
