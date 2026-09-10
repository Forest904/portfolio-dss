"""Existing-portfolio mean-variance optimization orchestration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal

from app.application.analysis import align_price_history, subtract_calendar_years
from app.application.errors import data_unavailable, invalid_input, optimization_failed
from app.application.estimators import (
    EstimatorId,
    EstimatorRegistry,
    ExpectedReturnComparison,
    compare_weights,
)
from app.application.valuation import (
    NEW_YORK,
    latest_completed_session_ceiling,
    normalize_positions,
    validate_supported_assets,
)
from app.domain import (
    DEFAULT_FINANCIAL_CONVENTIONS,
    AlignedReturnSample,
    AnalysisWindow,
    CurrentUniverseProvider,
    DataProvenance,
    DomainValidationError,
    ExpectedReturnEstimator,
    ExpectedReturnSignal,
    ExternalDataUnavailableError,
    MarketDataProvider,
    OptimizationConstraints,
    OptimizationRequest,
    OptimizationResult,
    OptimizationSolverError,
    PortfolioMetrics,
    PortfolioOptimizer,
    PortfolioWeights,
    PriceField,
    ReturnConvention,
    ReturnFrequency,
    RiskEstimate,
    RiskEstimator,
    evaluate_portfolio,
)


@dataclass(frozen=True, slots=True)
class AllocationComparison:
    asset_id: str
    current_weight: float
    recommended_weight: float
    weight_change: float


@dataclass(frozen=True, slots=True)
class PortfolioOptimizationReport:
    window: AnalysisWindow
    allocations: tuple[AllocationComparison, ...]
    current_metrics: PortfolioMetrics
    optimization: OptimizationResult
    expected_returns: ExpectedReturnSignal
    risk_estimate: RiskEstimate
    universe_as_of: date
    universe_provenance: DataProvenance
    price_provenance: DataProvenance
    risk_aversion: float
    max_weight: float | None
    assumptions: tuple[str, ...]
    diagnostics: tuple[str, ...]
    expected_return_comparison: ExpectedReturnComparison
    optimization_hash: str


class PortfolioOptimizationService:
    def __init__(
        self,
        universe_provider: CurrentUniverseProvider,
        market_data_provider: MarketDataProvider,
        expected_return_estimator: ExpectedReturnEstimator,
        risk_estimator: RiskEstimator,
        optimizer: PortfolioOptimizer,
        *,
        estimator_registry: EstimatorRegistry | None = None,
        clock: Callable[[], datetime] | None = None,
        maximum_consecutive_missing: int = 5,
    ) -> None:
        self._universe_provider = universe_provider
        self._market_data_provider = market_data_provider
        self._estimators = estimator_registry or EstimatorRegistry(expected_return_estimator)
        self._risk_estimator = risk_estimator
        self._optimizer = optimizer
        self._clock = clock or (lambda: datetime.now(UTC))
        self._maximum_consecutive_missing = maximum_consecutive_missing

    def optimize(
        self,
        positions: Sequence[tuple[str, Decimal]],
        *,
        risk_aversion: float,
        max_weight: float | None = None,
        start: date | None = None,
        end: date | None = None,
        expected_return_estimator: EstimatorId = "historical_mean",
    ) -> PortfolioOptimizationReport:
        normalized = normalize_positions(positions)
        asset_ids = tuple(ticker for ticker, _ in normalized)
        try:
            constraints = OptimizationConstraints(max_weight)
            if max_weight is not None and max_weight * len(asset_ids) < 1.0 - 1e-8:
                raise DomainValidationError("max_weight makes the budget constraint infeasible")
        except DomainValidationError as exc:
            raise invalid_input(
                "INFEASIBLE_CONSTRAINTS",
                str(exc),
                asset_count=len(asset_ids),
                max_weight=max_weight,
            ) from exc

        now = self._clock()
        requested_end = end or latest_completed_session_ceiling(now)
        if requested_end > now.astimezone(NEW_YORK).date():
            raise invalid_input(
                "INVALID_HISTORY_END", "The history end date cannot be in the future."
            )
        requested_start = start or subtract_calendar_years(requested_end, 3)
        if requested_start >= requested_end:
            raise invalid_input(
                "INVALID_HISTORY_WINDOW", "The history start date must precede the end date."
            )

        try:
            universe_snapshot = self._universe_provider.get_current_universe()
        except ExternalDataUnavailableError as exc:
            raise data_unavailable(str(exc), source="wikipedia") from exc
        validate_supported_assets(asset_ids, {asset.ticker for asset in universe_snapshot.assets})

        benchmark_id = universe_snapshot.universe.benchmark_asset_id
        requested_assets = (*asset_ids, benchmark_id)
        try:
            history = self._market_data_provider.get_price_history(
                requested_assets,
                requested_start,
                requested_end,
                ReturnFrequency.DAILY,
                PriceField.ADJUSTED_CLOSE,
                refresh_if_stale=end is None,
            )
        except ExternalDataUnavailableError as exc:
            raise data_unavailable(str(exc), source="yahoo_finance") from exc
        dates, aligned, excluded = align_price_history(
            history,
            requested_assets,
            maximum_consecutive_missing=self._maximum_consecutive_missing,
        )
        conventions = DEFAULT_FINANCIAL_CONVENTIONS
        sample = AlignedReturnSample(
            asset_ids=asset_ids,
            observed_on=dates[1:],
            returns=tuple(
                tuple(
                    float(values[index] / values[index - 1] - 1) for index in range(1, len(values))
                )
                for values in (aligned[asset_id] for asset_id in asset_ids)
            ),
            frequency=conventions.return_frequency,
            return_convention=ReturnConvention.SIMPLE,
            annualization_periods=conventions.annualization_periods,
            missing_data_policy=conventions.missing_data_policy,
        )
        benchmark_sample = replace(
            sample,
            asset_ids=(benchmark_id,),
            returns=(
                tuple(
                    float(aligned[benchmark_id][i] / aligned[benchmark_id][i - 1] - 1)
                    for i in range(1, len(dates))
                ),
            ),
        )
        benchmark_pair = self._estimators.estimate(benchmark_sample)
        pair = self._estimators.estimate(sample)
        signal = pair.selected(expected_return_estimator)
        risk = self._risk_estimator.estimate(sample)
        request = OptimizationRequest(signal, risk, risk_aversion, constraints)
        try:
            result = self._optimizer.optimize(request)
        except OptimizationSolverError as exc:
            raise optimization_failed(details=exc.details) from exc

        ending_values = tuple(
            float(quantity * aligned[asset_id][-1])
            for asset_id, (_, quantity) in zip(asset_ids, normalized, strict=True)
        )
        total = sum(ending_values)
        current_weights = PortfolioWeights(
            asset_ids, tuple(value / total for value in ending_values)
        )
        current_metrics = evaluate_portfolio(current_weights, signal, risk, risk_aversion)
        allocations = tuple(
            AllocationComparison(asset_id, current, recommended, recommended - current)
            for asset_id, current, recommended in zip(
                asset_ids, current_weights.weights, result.weights.weights, strict=True
            )
        )
        comparison = ExpectedReturnComparison(
            expected_return_estimator,
            pair,
            benchmark_pair,
            (
                compare_weights(
                    "sp500_proxy", PortfolioWeights((benchmark_id,), (1.0,)), benchmark_pair
                ),
                compare_weights("current", current_weights, pair),
                compare_weights("recommended", result.weights, pair),
                compare_weights(
                    "equal_weight",
                    PortfolioWeights(asset_ids, (1 / len(asset_ids),) * len(asset_ids)),
                    pair,
                ),
            ),
        )
        assumptions = (
            f"Expected-return estimator: {signal.estimator_name}; "
            "annualized arithmetic daily mean.",
            "Risk is annualized historical sample covariance using 252 trading periods per year",
            "The recommendation uses estimated parameters, not a guaranteed future "
            "allocation outcome",
            "Long-only, fully invested weights; no short selling, leverage, costs, taxes, "
            "or turnover constraint",
            "No missing-value imputation; selected assets use timestamp-intersection alignment",
            "Current weights use end-date market values; both portfolios use the same "
            "estimated inputs",
            "Current S&P 500 membership is used (survivorship bias applies)",
        )
        stable = {
            "positions": [[ticker, str(quantity)] for ticker, quantity in normalized],
            "requested_window": [requested_start.isoformat(), requested_end.isoformat()],
            "effective_window": [dates[0].isoformat(), dates[-1].isoformat()],
            "universe_hash": universe_snapshot.provenance.content_hash,
            "price_hash": history.provenance.content_hash,
            "risk_aversion": risk_aversion,
            "max_weight": max_weight,
            "recommended_weights": result.weights.weights,
            "assumptions": assumptions,
            "expected_return_comparison": asdict(comparison),
        }
        optimization_hash = hashlib.sha256(
            json.dumps(
                stable, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
            ).encode()
        ).hexdigest()
        return PortfolioOptimizationReport(
            window=AnalysisWindow(
                requested_start=requested_start,
                requested_end=requested_end,
                effective_start=dates[0],
                effective_end=dates[-1],
                aligned_price_observations=len(dates),
                return_observations=len(dates) - 1,
                excluded_observations=excluded,
            ),
            allocations=allocations,
            current_metrics=current_metrics,
            optimization=result,
            expected_returns=signal,
            risk_estimate=risk,
            universe_as_of=universe_snapshot.universe.as_of_date,
            universe_provenance=universe_snapshot.provenance,
            price_provenance=history.provenance,
            risk_aversion=risk_aversion,
            max_weight=max_weight,
            assumptions=assumptions,
            diagnostics=(*signal.diagnostics, *risk.diagnostics),
            expected_return_comparison=comparison,
            optimization_hash=optimization_hash,
        )
