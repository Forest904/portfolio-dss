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
    portfolio_risk_contributions,
)
from app.domain.catalog import UniverseSnapshot
from app.domain.conventions import FinancialConventions
from app.domain.frontier import (
    EfficientFrontierGenerator,
    EstimatedMetrics,
    FrontierRequest,
    FrontierResult,
    ProfileConfiguration,
    ProfileName,
)
from app.domain.market_data import PriceHistory


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
        "concentration_change",
        "binding_cap",
        "asset_expected_return",
        "risk_contribution",
        "risk_contribution_change",
        "equivalent_profile",
    ]
    subject: str
    comparison: str | None
    value: float
    unit: Literal["percentage_points", "weight_fraction", "annual_fraction", "hhi", "flag"]


@dataclass(frozen=True, slots=True)
class DecisionReason:
    id: str
    category: Literal["trade_off", "allocation", "diversification", "constraint", "model"]
    headline: str
    detail: str
    evidence_fact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DecisionExplanationSet:
    profile: ProfileName
    baseline: Literal["current", "equal_weight"]
    rule_version: str
    summary: str
    reasons: tuple[DecisionReason, ...]


@dataclass(frozen=True, slots=True)
class FrontierReport:
    window: AnalysisWindow
    frontier: FrontierResult
    references: tuple[ReferencePortfolio, ...]
    facts: tuple[DecisionFact, ...]
    explanations: tuple[DecisionExplanationSet, ...]
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
    holdings_capital: Decimal | None = None
    expected_return_comparison: ExpectedReturnComparison | None = None


def decision_facts(
    frontier: FrontierResult,
    references: tuple[ReferencePortfolio, ...],
    expected_returns: ExpectedReturnSignal,
    risk: RiskEstimate,
) -> tuple[tuple[DecisionFact, ...], tuple[str, ...]]:
    facts: list[DecisionFact] = []
    current = next((reference for reference in references if reference.id == "current"), None)
    baseline = current or next(
        reference for reference in references if reference.id == "equal_weight"
    )
    baseline_risk = portfolio_risk_contributions(baseline.weights, risk)
    diagnostics: list[str] = []
    if baseline_risk is None:
        diagnostics.append(
            f"Relative risk contribution is unavailable for {baseline.id}: "
            "modeled variance is effectively zero."
        )
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
        for asset, estimate in zip(
            expected_returns.asset_ids, expected_returns.expected_returns, strict=True
        ):
            facts.append(
                DecisionFact(
                    f"{profile.name}.{asset}.asset_expected_return",
                    profile.name,
                    "asset_expected_return",
                    asset,
                    None,
                    estimate,
                    "annual_fraction",
                )
            )
        if baseline is not None:
            for asset, weight, previous in zip(
                point.weights.asset_ids,
                point.weights.weights,
                baseline.weights.weights,
                strict=True,
            ):
                facts.append(
                    DecisionFact(
                        f"{profile.name}.{asset}.allocation_change",
                        profile.name,
                        "allocation_change",
                        asset,
                        baseline.id,
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
        baseline_hhi = math.fsum(weight * weight for weight in baseline.weights.weights)
        facts.append(
            DecisionFact(
                f"{profile.name}.{baseline.id}.concentration_change",
                profile.name,
                "concentration_change",
                point.id,
                baseline.id,
                math.fsum(w * w for w in point.weights.weights) - baseline_hhi,
                "hhi",
            )
        )
        point_risk = portfolio_risk_contributions(point.weights, risk)
        if point_risk is None:
            diagnostics.append(
                f"Relative risk contribution is unavailable for {profile.name}: "
                "modeled variance is effectively zero."
            )
        if point_risk is not None and baseline_risk is not None:
            for selected_item, baseline_item in zip(point_risk, baseline_risk, strict=True):
                facts.extend(
                    (
                        DecisionFact(
                            f"{profile.name}.{selected_item.asset_id}.risk_contribution",
                            profile.name,
                            "risk_contribution",
                            selected_item.asset_id,
                            point.id,
                            selected_item.relative_contribution,
                            "weight_fraction",
                        ),
                        DecisionFact(
                            f"{profile.name}.{baseline.id}.{selected_item.asset_id}.risk_contribution",
                            profile.name,
                            "risk_contribution",
                            selected_item.asset_id,
                            baseline.id,
                            baseline_item.relative_contribution,
                            "weight_fraction",
                        ),
                        DecisionFact(
                            f"{profile.name}.{selected_item.asset_id}.risk_contribution_change",
                            profile.name,
                            "risk_contribution_change",
                            selected_item.asset_id,
                            baseline.id,
                            100
                            * (
                                selected_item.relative_contribution
                                - baseline_item.relative_contribution
                            ),
                            "percentage_points",
                        ),
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
        equivalents = sorted(
            other.name
            for other in frontier.profiles
            if other.name != profile.name and other.point_id == profile.point_id
        )
        for other in equivalents:
            facts.append(
                DecisionFact(
                    f"{profile.name}.{other}.equivalent_profile",
                    profile.name,
                    "equivalent_profile",
                    profile.name,
                    other,
                    1.0,
                    "flag",
                )
            )
    return tuple(facts), tuple(dict.fromkeys(diagnostics))


def decision_explanations(
    frontier: FrontierResult,
    facts: tuple[DecisionFact, ...],
    baseline: Literal["current", "equal_weight"],
    estimator_name: str,
) -> tuple[DecisionExplanationSet, ...]:
    """Render stable, cautious explanations exclusively from structured facts."""

    baseline_label = (
        "your current portfolio" if baseline == "current" else "an equal-weight portfolio"
    )

    def signed(value: float) -> str:
        return f"{value:+.1f}"

    results: list[DecisionExplanationSet] = []
    for profile in frontier.profiles:
        selected = tuple(fact for fact in facts if fact.profile == profile.name)
        by_id = {fact.id: fact for fact in selected}
        return_fact = by_id[f"{profile.name}.{baseline}.expected_return_change"]
        volatility_fact = by_id[f"{profile.name}.{baseline}.volatility_change"]

        def movement(value: float, noun: str) -> str:
            if abs(value) < 0.1:
                return f"estimated annual {noun} is effectively unchanged"
            direction = "higher" if value > 0 else "lower"
            return f"estimated annual {noun} is {abs(value):.1f} percentage points {direction}"

        summary = (
            f"Compared with {baseline_label}, {movement(return_fact.value, 'return')} and "
            f"{movement(volatility_fact.value, 'volatility')}."
        )
        candidates: list[tuple[int, float, DecisionReason]] = []
        candidates.append(
            (
                20,
                max(abs(return_fact.value), abs(volatility_fact.value)),
                DecisionReason(
                    f"{profile.name}.trade_off",
                    "trade_off",
                    "The recommendation makes an explicit return–risk trade-off",
                    f"Versus {baseline_label}: {movement(return_fact.value, 'return')} "
                    f"and {movement(volatility_fact.value, 'volatility')}. "
                    "These are estimates, not guarantees.",
                    (return_fact.id, volatility_fact.id),
                ),
            )
        )
        caps = tuple(fact for fact in selected if fact.kind == "binding_cap")
        if caps:
            names = ", ".join(fact.subject for fact in caps[:3])
            extra = f" and {len(caps) - 3} more" if len(caps) > 3 else ""
            candidates.append(
                (
                    5,
                    max(fact.value for fact in caps),
                    DecisionReason(
                        f"{profile.name}.binding_caps",
                        "constraint",
                        "The weight limit changes what is feasible",
                        f"{names}{extra} reach the configured maximum weight. The model "
                        "cannot allocate more to them even when the joint return–risk "
                        "calculation would otherwise do so.",
                        tuple(fact.id for fact in caps),
                    ),
                )
            )
        equivalents = tuple(fact for fact in selected if fact.kind == "equivalent_profile")
        if equivalents:
            candidates.append(
                (
                    4,
                    1.0,
                    DecisionReason(
                        f"{profile.name}.equivalent_profiles",
                        "constraint",
                        "Some preference choices lead to the same portfolio",
                        "The available assets and constraints collapse this profile onto "
                        + ", ".join(str(fact.comparison) for fact in equivalents)
                        + ". No artificial difference is shown.",
                        tuple(fact.id for fact in equivalents),
                    ),
                )
            )
        changes = sorted(
            (
                fact
                for fact in selected
                if fact.kind == "allocation_change"
                and fact.comparison == baseline
                and abs(fact.value) >= 0.5
            ),
            key=lambda fact: (-abs(fact.value), fact.id),
        )[:2]
        for change in changes:
            evidence = [change.id]
            return_evidence = by_id.get(f"{profile.name}.{change.subject}.asset_expected_return")
            risk_change = by_id.get(f"{profile.name}.{change.subject}.risk_contribution_change")
            baseline_risk_fact = by_id.get(
                f"{profile.name}.{baseline}.{change.subject}.risk_contribution"
            )
            selected_risk_fact = by_id.get(f"{profile.name}.{change.subject}.risk_contribution")
            context: list[str] = []
            if return_evidence:
                evidence.append(return_evidence.id)
                context.append(
                    f"its model estimate is {100 * return_evidence.value:.1f}% annual return"
                )
            if (
                risk_change
                and baseline_risk_fact
                and selected_risk_fact
                and abs(risk_change.value) >= 0.5
            ):
                evidence.extend((baseline_risk_fact.id, selected_risk_fact.id, risk_change.id))
                context.append(
                    "its share of modeled risk moves from "
                    f"{100 * baseline_risk_fact.value:.1f}% to "
                    f"{100 * selected_risk_fact.value:.1f}%"
                )
            suffix = "; ".join(context)
            candidates.append(
                (
                    30,
                    abs(change.value),
                    DecisionReason(
                        f"{profile.name}.{change.subject}.allocation",
                        "allocation",
                        f"{change.subject} is {'increased' if change.value > 0 else 'reduced'}",
                        f"Its target weight changes by {signed(change.value)} percentage "
                        f"points versus {baseline_label}"
                        + (f"; {suffix}" if suffix else "")
                        + ". These facts put the shift in context; the allocation itself comes "
                        "from the profile target and the assets' joint expected returns and "
                        "covariances.",
                        tuple(evidence),
                    ),
                )
            )
        concentration = by_id.get(f"{profile.name}.{baseline}.concentration_change")
        if concentration and abs(concentration.value) >= 0.01:
            candidates.append(
                (
                    40,
                    abs(concentration.value),
                    DecisionReason(
                        f"{profile.name}.concentration_change",
                        "diversification",
                        "Holdings become "
                        f"{'more' if concentration.value > 0 else 'less'} concentrated",
                        "The HHI concentration measure changes by "
                        f"{concentration.value:+.3f} versus {baseline_label}; higher HHI "
                        "means weights are concentrated in fewer names.",
                        (concentration.id,),
                    ),
                )
            )
        largest = next(fact for fact in selected if fact.kind == "largest_holding")
        candidates.extend(
            (
                (
                    80,
                    largest.value,
                    DecisionReason(
                        f"{profile.name}.largest_holding_context",
                        "diversification",
                        "The largest target holding remains visible",
                        f"{largest.subject} is the largest position at "
                        f"{100 * largest.value:.1f}% of the portfolio.",
                        (largest.id,),
                    ),
                ),
                (
                    90,
                    0.0,
                    DecisionReason(
                        f"{profile.name}.model_basis",
                        "model",
                        "The result depends on an estimated model",
                        f"The {estimator_name} expected-return signal and historical "
                        "covariance are used together. Costs, taxes, turnover and guaranteed "
                        "outcomes are not modeled.",
                        (),
                    ),
                ),
            )
        )
        ordered = sorted(candidates, key=lambda item: (item[0], -item[1], item[2].id))
        reasons = tuple(item[2] for item in ordered[:5])
        if len(reasons) < 3:
            raise RuntimeError("explanation rules must produce at least three reasons")
        results.append(
            DecisionExplanationSet(
                profile.name,
                baseline,
                "decision-explanations-v1",
                summary,
                reasons,
            )
        )
    return tuple(results)


class PortfolioFrontierService:
    @property
    def configuration_signature(self) -> str:
        """Stable cache identity for the configured model and profile implementations."""
        return repr(
            (
                "frontier-report-v4",
                self._estimators.identity("historical_mean"),
                self._estimators.identity("simple_forecast"),
                self._profiles,
                type(self._returns).__module__,
                type(self._returns).__qualname__,
                type(self._risk).__module__,
                type(self._risk).__qualname__,
                type(self._generator).__module__,
                type(self._generator).__qualname__,
            )
        )

    def __init__(
        self,
        universe_provider: CurrentUniverseProvider,
        market_data_provider: MarketDataProvider,
        expected_return_estimator: ExpectedReturnEstimator,
        risk_estimator: RiskEstimator,
        generator: EfficientFrontierGenerator,
        *,
        profiles: ProfileConfiguration | None = None,
        estimator_registry: EstimatorRegistry | None = None,
        clock: Callable[[], datetime] | None = None,
        maximum_consecutive_missing: int = 5,
    ) -> None:
        self._universe = universe_provider
        self._prices = market_data_provider
        self._returns = expected_return_estimator
        self._estimators = estimator_registry or EstimatorRegistry(expected_return_estimator)
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
        expected_return_estimator: EstimatorId = "historical_mean",
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

        return self.build_report(
            asset_ids,
            benchmark_id,
            dates,
            aligned,
            excluded,
            universe,
            history,
            constraints,
            normalized,
            expected_return_estimator=expected_return_estimator,
        )

    def build_report(
        self,
        asset_ids: tuple[str, ...],
        benchmark_id: str,
        dates: tuple[date, ...],
        aligned: dict[str, tuple[Decimal, ...]],
        excluded: tuple[tuple[str, int], ...],
        universe: UniverseSnapshot,
        history: PriceHistory,
        constraints: OptimizationConstraints,
        normalized: Sequence[tuple[str, Decimal]] = (),
        *,
        expected_return_estimator: EstimatorId = "historical_mean",
    ) -> FrontierReport:
        """Calculate alternatives from one validated snapshot, with optional real holdings."""
        conventions = DEFAULT_FINANCIAL_CONVENTIONS
        max_weight = constraints.max_weight
        requested_start, requested_end = history.start, history.end

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
        pair = self._estimators.estimate(selected_sample)
        benchmark_pair = self._estimators.estimate(benchmark_sample)
        signal = pair.selected(expected_return_estimator)
        risk = self._risk.estimate(selected_sample)
        benchmark_signal = benchmark_pair.selected(expected_return_estimator)
        benchmark_risk = self._risk.estimate(benchmark_sample)
        try:
            frontier = self._generator.generate(
                FrontierRequest(signal, risk, constraints, self._profiles)
            )
        except OptimizationSolverError as exc:
            raise optimization_failed(details=exc.details) from exc
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

        references: tuple[ReferencePortfolio, ...] = (
            reference("equal_weight", equal, signal, risk),
            reference(
                "sp500_proxy",
                PortfolioWeights((benchmark_id,), (1.0,)),
                benchmark_signal,
                benchmark_risk,
            ),
        )
        total: Decimal | None = None
        current: ReferencePortfolio | None = None
        if normalized:
            values = tuple(quantity * aligned[asset][-1] for asset, quantity in normalized)
            total = sum(values, Decimal(0))
            current_weights = PortfolioWeights(
                asset_ids, tuple(float(value / total) for value in values)
            )
            current = reference("current", current_weights, signal, risk)
            references = (current, *references)
        comparison = ExpectedReturnComparison(
            expected_return_estimator,
            pair,
            benchmark_pair,
            tuple(
                compare_weights(r.id, r.weights, benchmark_pair if r.id == "sp500_proxy" else pair)
                for r in references
            )
            + tuple(
                compare_weights(
                    p.name,
                    next(point.weights for point in frontier.points if point.id == p.point_id),
                    pair,
                )
                for p in frontier.profiles
            ),
        )
        assumptions = (
            f"Allocation estimator: {signal.estimator_name}. "
            "Forecast uses a constant future daily mean.",
            "Returns are estimated annual arithmetic means, "
            "not observed CAGR or guaranteed future returns.",
            "Volatility is estimated from historical sample covariance, "
            "annualized using 252 trading periods.",
            "All alternatives and references share the same "
            "adjusted-close daily simple-return observations.",
            "Profile fractions locate targets between minimum-variance return "
            "and maximum achievable return; "
            "they are relative preferences, not probabilities or absolute risk categories.",
            (
                "Only selected stocks are investable. "
                if normalized
                else "Only eligible S&P 500 stocks are investable. "
            )
            + "SPY is the S&P 500 total-return ETF proxy reference.",
            "Long-only, fully invested; no leverage, costs, taxes, or turnover constraint.",
            (
                "Current weights use end-date market values; equal weights cover selected stocks."
                if normalized
                else "Equal weights cover eligible stocks; no current holdings supplied."
            ),
            "No missing-value imputation; timestamp-intersection alignment is used.",
            "Current S&P 500 membership is used; survivorship bias applies.",
        )
        facts, fact_diagnostics = decision_facts(frontier, references, signal, risk)
        baseline_id: Literal["current", "equal_weight"] = (
            "current" if current is not None else "equal_weight"
        )
        explanations = decision_explanations(frontier, facts, baseline_id, signal.estimator_name)
        report = FrontierReport(
            window=AnalysisWindow(
                requested_start,
                requested_end,
                dates[0],
                dates[-1],
                len(dates),
                len(dates) - 1,
                excluded,
            ),
            frontier=frontier,
            references=references,
            facts=facts,
            explanations=explanations,
            expected_return_model=signal,
            risk_model=risk,
            benchmark_expected_return_model=benchmark_signal,
            benchmark_risk_model=benchmark_risk,
            constraints=constraints,
            profile_configuration=self._profiles,
            conventions=conventions,
            universe_as_of=universe.universe.as_of_date,
            universe_provenance=universe.provenance,
            price_provenance=history.provenance,
            assumptions=assumptions,
            diagnostics=(
                *signal.diagnostics,
                *risk.diagnostics,
                *benchmark_signal.diagnostics,
                *benchmark_risk.diagnostics,
                *frontier.diagnostics,
                *fact_diagnostics,
            ),
            report_hash="",
            holdings_capital=total,
            expected_return_comparison=comparison,
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
