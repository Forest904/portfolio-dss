"""Pure historical portfolio analytics and typed calculation results."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date

from app.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class HistoricalSeriesPoint:
    observed_on: date
    daily_return: float | None
    cumulative_return: float


@dataclass(frozen=True, slots=True)
class PerformanceSummary:
    total_return: float
    annualized_return: float
    annualized_volatility: float


@dataclass(frozen=True, slots=True)
class LabelledMatrix:
    asset_ids: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]


@dataclass(frozen=True, slots=True)
class ConcentrationComponent:
    id: str
    weight: float


@dataclass(frozen=True, slots=True)
class ConcentrationSummary:
    components: tuple[ConcentrationComponent, ...]
    largest_id: str
    largest_weight: float
    top_three_weight: float
    hhi: float
    effective_count: float


@dataclass(frozen=True, slots=True)
class HistoricalAnalytics:
    current_series: tuple[HistoricalSeriesPoint, ...]
    equal_weight_series: tuple[HistoricalSeriesPoint, ...]
    benchmark_series: tuple[HistoricalSeriesPoint, ...]
    current_performance: PerformanceSummary
    equal_weight_performance: PerformanceSummary
    benchmark_performance: PerformanceSummary
    covariance: LabelledMatrix
    correlation: LabelledMatrix
    asset_concentration: ConcentrationSummary
    sector_concentration: ConcentrationSummary
    undefined_correlation_assets: tuple[str, ...]
    ending_asset_weights: tuple[float, ...]


def _returns(values: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(values[index] / values[index - 1] - 1.0 for index in range(1, len(values)))


def _series(
    dates: tuple[date, ...], values: tuple[float, ...]
) -> tuple[HistoricalSeriesPoint, ...]:
    initial = values[0]
    returns = _returns(values)
    return (
        HistoricalSeriesPoint(dates[0], None, 0.0),
        *(
            HistoricalSeriesPoint(observed_on, returns[index - 1], value / initial - 1.0)
            for index, (observed_on, value) in enumerate(
                zip(dates[1:], values[1:], strict=True), start=1
            )
        ),
    )


def _performance(values: tuple[float, ...], annualization_periods: int) -> PerformanceSummary:
    returns = _returns(values)
    total_return = values[-1] / values[0] - 1.0
    annualized_return = (values[-1] / values[0]) ** (annualization_periods / len(returns)) - 1.0
    annualized_volatility = statistics.stdev(returns) * math.sqrt(annualization_periods)
    return PerformanceSummary(total_return, annualized_return, annualized_volatility)


def _sample_covariance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    return math.fsum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    ) / (len(left) - 1)


def _matrices(
    asset_ids: tuple[str, ...],
    asset_returns: tuple[tuple[float, ...], ...],
    annualization_periods: int,
) -> tuple[LabelledMatrix, LabelledMatrix, tuple[str, ...]]:
    daily_covariance = tuple(
        tuple(_sample_covariance(left, right) for right in asset_returns) for left in asset_returns
    )
    variances = tuple(daily_covariance[index][index] for index in range(len(asset_ids)))
    undefined = tuple(
        asset_id
        for asset_id, variance in zip(asset_ids, variances, strict=True)
        if math.isclose(variance, 0.0, abs_tol=1e-30)
    )
    covariance = tuple(
        tuple(value * annualization_periods for value in row) for row in daily_covariance
    )
    correlation = tuple(
        tuple(
            None
            if asset_ids[row_index] in undefined or asset_ids[column_index] in undefined
            else max(
                -1.0,
                min(
                    1.0,
                    daily_covariance[row_index][column_index]
                    / math.sqrt(variances[row_index] * variances[column_index]),
                ),
            )
            for column_index in range(len(asset_ids))
        )
        for row_index in range(len(asset_ids))
    )
    return (
        LabelledMatrix(asset_ids, covariance),
        LabelledMatrix(asset_ids, correlation),
        undefined,
    )


def concentration(weights_by_id: dict[str, float]) -> ConcentrationSummary:
    if not weights_by_id or any(weight < 0.0 for weight in weights_by_id.values()):
        raise DomainValidationError("concentration weights must be non-empty and non-negative")
    total = math.fsum(weights_by_id.values())
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-8):
        raise DomainValidationError("concentration weights must sum to one")
    components = tuple(
        ConcentrationComponent(identifier, weight)
        for identifier, weight in sorted(
            weights_by_id.items(), key=lambda item: (-item[1], item[0])
        )
    )
    hhi = math.fsum(component.weight**2 for component in components)
    return ConcentrationSummary(
        components=components,
        largest_id=components[0].id,
        largest_weight=components[0].weight,
        top_three_weight=math.fsum(component.weight for component in components[:3]),
        hhi=hhi,
        effective_count=1.0 / hhi,
    )


def calculate_historical_analytics(
    *,
    asset_ids: tuple[str, ...],
    benchmark_asset_id: str,
    dates: tuple[date, ...],
    prices: dict[str, tuple[float, ...]],
    quantities: tuple[float, ...],
    sectors: tuple[str, ...],
    annualization_periods: int,
) -> HistoricalAnalytics:
    """Calculate buy-and-hold analytics from already aligned, positive prices."""
    if len(dates) < 3:
        raise DomainValidationError("at least three aligned prices are required")
    if len(asset_ids) != len(quantities) or len(asset_ids) != len(sectors):
        raise DomainValidationError("asset metadata and quantities must align")
    if set(prices) != {*asset_ids, benchmark_asset_id}:
        raise DomainValidationError("price identifiers do not match the requested assets")
    if any(quantity <= 0.0 or not math.isfinite(quantity) for quantity in quantities):
        raise DomainValidationError("quantities must be finite and positive")
    if any(
        len(values) != len(dates)
        or any(value <= 0.0 or not math.isfinite(value) for value in values)
        for values in prices.values()
    ):
        raise DomainValidationError("prices must align with dates and be finite and positive")

    current_values = tuple(
        math.fsum(
            quantities[index] * prices[asset_id][date_index]
            for index, asset_id in enumerate(asset_ids)
        )
        for date_index in range(len(dates))
    )
    equal_weight_values = tuple(
        math.fsum(prices[asset_id][date_index] / prices[asset_id][0] for asset_id in asset_ids)
        / len(asset_ids)
        for date_index in range(len(dates))
    )
    benchmark_values = tuple(
        value / prices[benchmark_asset_id][0] for value in prices[benchmark_asset_id]
    )
    ending_values = tuple(
        quantities[index] * prices[asset_id][-1] for index, asset_id in enumerate(asset_ids)
    )
    ending_total = math.fsum(ending_values)
    ending_weights = tuple(value / ending_total for value in ending_values)
    asset_weights = dict(zip(asset_ids, ending_weights, strict=True))
    sector_weights: dict[str, float] = {}
    for sector, weight in zip(sectors, ending_weights, strict=True):
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

    asset_returns = tuple(_returns(prices[asset_id]) for asset_id in asset_ids)
    covariance, correlation, undefined = _matrices(asset_ids, asset_returns, annualization_periods)
    return HistoricalAnalytics(
        current_series=_series(dates, current_values),
        equal_weight_series=_series(dates, equal_weight_values),
        benchmark_series=_series(dates, benchmark_values),
        current_performance=_performance(current_values, annualization_periods),
        equal_weight_performance=_performance(equal_weight_values, annualization_periods),
        benchmark_performance=_performance(benchmark_values, annualization_periods),
        covariance=covariance,
        correlation=correlation,
        asset_concentration=concentration(asset_weights),
        sector_concentration=concentration(sector_weights),
        undefined_correlation_assets=undefined,
        ending_asset_weights=ending_weights,
    )
