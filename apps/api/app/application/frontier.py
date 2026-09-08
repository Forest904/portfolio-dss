"""One aligned snapshot for frontier alternatives and comparable reference estimates."""

import hashlib
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from app.application.analysis import align_price_history, subtract_calendar_years
from app.application.errors import data_unavailable, invalid_input, optimization_failed
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
    ExpectedReturnEstimator,
    ExpectedReturnSignal,
    ExternalDataUnavailableError,
    MarketDataProvider,
    OptimizationConstraints,
    OptimizationSolverError,
    PortfolioWeights,
    RiskEstimate,
    RiskEstimator,
    evaluate_portfolio,
)
from app.domain.conventions import FinancialConventions
from app.domain.frontier import (
    EfficientFrontierGenerator,
    EstimatedMetrics,
    FrontierRequest,
    FrontierResult,
    ProfileConfiguration,
    ProfileName,
)


@dataclass(frozen=True, slots=True)
class ReferencePortfolio:
    id: Literal["current", "equal_weight", "sp500_proxy"]
    weights: PortfolioWeights
    metrics: EstimatedMetrics
    constraint_status: Literal["valid", "exceeds_max_weight", "outside_investable_universe"]


@dataclass(frozen=True, slots=True)
class DecisionFact:
    id: str
    profile: ProfileName
    kind: Literal[
        "expected_return_change",
        "volatility_change",
        "allocation_change",
        "largest_holding",
        "concentration",
        "binding_cap",
    ]
    subject: str
    comparison: str | None
    value: float
    unit: Literal["percentage_points", "weight_fraction", "hhi"]


@dataclass(frozen=True, slots=True)
class FrontierReport:
    window: AnalysisWindow
    frontier: FrontierResult
    references: tuple[ReferencePortfolio, ...]
    facts: tuple[DecisionFact, ...]
    expected_return_model: ExpectedReturnSignal
    risk_model: RiskEstimate
    benchmark_expected_return_model: ExpectedReturnSignal
    benchmark_risk_model: RiskEstimate
    constraints: OptimizationConstraints
    profile_configuration: ProfileConfiguration
    conventions: FinancialConventions
    universe_as_of: date
    universe_provenance: DataProvenance
    price_provenance: DataProvenance
    assumptions: tuple[str, ...]
    diagnostics: tuple[str, ...]
    report_hash: str


def decision_facts(
    frontier: FrontierResult,
    references: tuple[ReferencePortfolio, ...],
) -> tuple[DecisionFact, ...]:
    facts: list[DecisionFact] = []
    current = next(reference for reference in references if reference.id == "current")
    for profile in frontier.profiles:
        point = next(point for point in frontier.points if point.id == profile.point_id)
        for reference in references:
            for kind, value in (
                (
                    "expected_return_change",
                    point.metrics.expected_return - reference.metrics.expected_return,
                ),
                ("volatility_change", point.metrics.volatility - reference.metrics.volatility),
            ):
                facts.append(
                    DecisionFact(
                        f"{profile.name}.{reference.id}.{kind}",
                        profile.name,
                        "expected_return_change"
                        if kind == "expected_return_change"
                        else "volatility_change",
                        point.id,
                        reference.id,
                        100 * value,
                        "percentage_points",
                    )
                )
        for asset, weight, previous in zip(
            point.weights.asset_ids, point.weights.weights, current.weights.weights, strict=True
        ):
            facts.append(
                DecisionFact(
                    f"{profile.name}.{asset}.allocation_change",
                    profile.name,
                    "allocation_change",
                    asset,
                    "current",
                    100 * (weight - previous),
                    "percentage_points",
                )
            )
        largest = max(range(len(point.weights.weights)), key=lambda i: point.weights.weights[i])
        facts.append(
            DecisionFact(
                f"{profile.name}.largest_holding",
                profile.name,
                "largest_holding",
                point.weights.asset_ids[largest],
                None,
                point.weights.weights[largest],
                "weight_fraction",
            )
        )
        facts.append(
            DecisionFact(
                f"{profile.name}.concentration",
                profile.name,
                "concentration",
                point.id,
                None,
                math.fsum(w * w for w in point.weights.weights),
                "hhi",
            )
        )
        for asset in point.solver.binding_asset_ids:
            weight = point.weights.weights[point.weights.asset_ids.index(asset)]
            facts.append(
                DecisionFact(
                    f"{profile.name}.{asset}.binding_cap",
                    profile.name,
                    "binding_cap",
                    asset,
                    None,
                    weight,
                    "weight_fraction",
                )
            )
    return tuple(facts)


class PortfolioFrontierService:
    def __init__(
        self,
        universe_provider: CurrentUniverseProvider,
        market_data_provider: MarketDataProvider,
        expected_return_estimator: ExpectedReturnEstimator,
        risk_estimator: RiskEstimator,
        generator: EfficientFrontierGenerator,
        *,
        profiles: ProfileConfiguration | None = None,
        clock: Callable[[], datetime] | None = None,
        maximum_consecutive_missing: int = 5,
    ) -> None:
        self._universe = universe_provider
        self._prices = market_data_provider
        self._returns = expected_return_estimator
        self._risk = risk_estimator
        self._generator = generator
        self._profiles = profiles or ProfileConfiguration()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._maximum_consecutive_missing = maximum_consecutive_missing

    def generate(
        self,
        positions: Sequence[tuple[str, Decimal]],
        *,
        max_weight: float | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> FrontierReport:
        normalized = normalize_positions(positions)
        asset_ids = tuple(asset for asset, _ in normalized)
        constraints = OptimizationConstraints(max_weight)
        if max_weight is not None and max_weight * len(asset_ids) < 1 - 1e-8:
            raise invalid_input(
                "INFEASIBLE_CONSTRAINTS", "The maximum weight cannot fund the portfolio."
            )
        now = self._clock()
        requested_end = end or latest_completed_session_ceiling(now)
        requested_start = start or subtract_calendar_years(requested_end, 3)
        if requested_end > now.astimezone(NEW_YORK).date():
            raise invalid_input(
                "INVALID_HISTORY_END", "The history end date cannot be in the future."
            )
        if requested_start >= requested_end:
            raise invalid_input(
                "INVALID_HISTORY_WINDOW", "The history start date must precede the end date."
            )
        try:
            universe = self._universe.get_current_universe()
        except ExternalDataUnavailableError as exc:
            raise data_unavailable(str(exc), source="wikipedia") from exc
        validate_supported_assets(asset_ids, {asset.ticker for asset in universe.assets})
        benchmark_id = universe.universe.benchmark_asset_id
        requested_assets = (*asset_ids, benchmark_id)
        conventions = DEFAULT_FINANCIAL_CONVENTIONS
        try:
            history = self._prices.get_price_history(
                requested_assets,
                requested_start,
                requested_end,
                conventions.return_frequency,
                conventions.price_field,
                refresh_if_stale=end is None,
            )
        except ExternalDataUnavailableError as exc:
            raise data_unavailable(str(exc), source="yahoo_finance") from exc
        dates, aligned, excluded = align_price_history(
            history,
            requested_assets,
            maximum_consecutive_missing=self._maximum_consecutive_missing,
        )

        def sample(ids: tuple[str, ...]) -> AlignedReturnSample:
            return AlignedReturnSample(
                ids,
                dates[1:],
                tuple(
                    tuple(
                        float(aligned[asset][i] / aligned[asset][i - 1] - 1)
                        for i in range(1, len(dates))
                    )
                    for asset in ids
                ),
                conventions.return_frequency,
                conventions.return_convention,
                conventions.annualization_periods,
                conventions.missing_data_policy,
            )

        selected_sample, benchmark_sample = sample(asset_ids), sample((benchmark_id,))
        signal, risk = self._returns.estimate(selected_sample), self._risk.estimate(selected_sample)
        benchmark_signal = self._returns.estimate(benchmark_sample)
        benchmark_risk = self._risk.estimate(benchmark_sample)
        try:
            frontier = self._generator.generate(
                FrontierRequest(signal, risk, constraints, self._profiles)
            )
        except OptimizationSolverError as exc:
            raise optimization_failed(details=exc.details) from exc
        values = tuple(quantity * aligned[asset][-1] for asset, quantity in normalized)
        total = sum(values)
        current = PortfolioWeights(asset_ids, tuple(float(value / total) for value in values))
        equal = PortfolioWeights(asset_ids, tuple(1 / len(asset_ids) for _ in asset_ids))

        def reference(
            name: Literal["current", "equal_weight", "sp500_proxy"],
            weights: PortfolioWeights,
            means: ExpectedReturnSignal,
            covariance: RiskEstimate,
        ) -> ReferencePortfolio:
            metrics = evaluate_portfolio(weights, means, covariance, 0)
            return ReferencePortfolio(
                name,
                weights,
                EstimatedMetrics(metrics.expected_return, metrics.variance, metrics.volatility),
                "outside_investable_universe"
                if name == "sp500_proxy"
                else "exceeds_max_weight"
                if max_weight is not None and max(weights.weights) > max_weight + 1e-8
                else "valid",
            )

        references = (
            reference("current", current, signal, risk),
            reference("equal_weight", equal, signal, risk),
            reference(
                "sp500_proxy",
                PortfolioWeights((benchmark_id,), (1.0,)),
                benchmark_signal,
                benchmark_risk,
            ),
        )
        assumptions = (
            "Returns are estimated annual arithmetic means, "
            "not observed CAGR or guaranteed future returns.",
            "Volatility is estimated from historical sample covariance, "
            "annualized using 252 trading periods.",
            "All alternatives and references share the same "
            "adjusted-close daily simple-return observations.",
            "Profile fractions locate targets between minimum-variance return "
            "and maximum achievable return; "
            "they are relative preferences, not probabilities or absolute risk categories.",
            "Only selected stocks are investable. "
            "SPY is the S&P 500 total-return ETF proxy reference.",
            "Long-only, fully invested; no leverage, costs, taxes, or turnover constraint.",
            "Current weights use end-date market values; equal weights cover selected stocks.",
            "No missing-value imputation; timestamp-intersection alignment is used.",
            "Current S&P 500 membership is used; survivorship bias applies.",
        )
        report = FrontierReport(
            AnalysisWindow(
                requested_start,
                requested_end,
                dates[0],
                dates[-1],
                len(dates),
                len(dates) - 1,
                excluded,
            ),
            frontier,
            references,
            decision_facts(frontier, references),
            signal,
            risk,
            benchmark_signal,
            benchmark_risk,
            constraints,
            self._profiles,
            conventions,
            universe.universe.as_of_date,
            universe.provenance,
            history.provenance,
            assumptions,
            (
                *signal.diagnostics,
                *risk.diagnostics,
                *benchmark_signal.diagnostics,
                *benchmark_risk.diagnostics,
                *frontier.diagnostics,
            ),
            "",
        )
        stable = asdict(report)
        for key in ("universe_provenance", "price_provenance"):
            stable[key].pop("retrieved_at")
        stable["positions"] = [(asset, str(quantity)) for asset, quantity in normalized]
        digest = hashlib.sha256(
            json.dumps(
                stable, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
            ).encode()
        ).hexdigest()
        return replace(report, report_hash=digest)
