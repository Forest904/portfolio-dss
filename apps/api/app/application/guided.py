"""Full-universe construction without current holdings or framework dependencies."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from app.application.analysis import subtract_calendar_years
from app.application.errors import data_unavailable, invalid_input
from app.application.estimators import EstimatorId
from app.application.frontier import FrontierReport, PortfolioFrontierService
from app.application.valuation import latest_completed_session_ceiling
from app.domain import (
    DEFAULT_FINANCIAL_CONVENTIONS,
    CurrentUniverseProvider,
    ExternalDataUnavailableError,
    OptimizationConstraints,
)
from app.domain.bulk_history import BulkHistoryProvider, HistoryFailure
from app.domain.frontier import ProfileName
from app.domain.guided import DollarAllocation, PreferenceResult, allocate_capital
from app.domain.market_data import DataProvenance, PriceHistory
from app.domain.models import Currency


def stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class Coverage:
    total: int
    eligible: int
    excluded: tuple[HistoryFailure, ...]
    policy: str = "complete-spy-sessions-v1"
    minimum_fraction: float = 0.9


@dataclass(frozen=True, slots=True)
class GuidedModel:
    report: FrontierReport
    coverage: Coverage
    price_sources: tuple[DataProvenance, ...]
    model_hash: str


class GuidedModelCache(Protocol):
    def get_model(self, key: str) -> GuidedModel | None: ...
    def put_model(self, key: str, model: GuidedModel) -> None: ...


@dataclass(frozen=True, slots=True)
class CapitalAlternative:
    profile: ProfileName
    allocations: tuple[DollarAllocation, ...]


@dataclass(frozen=True, slots=True)
class GuidedReport:
    preference: PreferenceResult
    capital: Decimal
    currency: str
    alternatives: tuple[CapitalAlternative, ...]
    model: GuidedModel
    report_hash: str


def personalize(model: GuidedModel, preference: PreferenceResult, capital: Decimal) -> GuidedReport:
    alternatives = tuple(
        CapitalAlternative(
            p.name,
            allocate_capital(
                capital,
                next(
                    point.weights
                    for point in model.report.frontier.points
                    if point.id == p.point_id
                ),
            ),
        )
        for p in model.report.frontier.profiles
    )
    return GuidedReport(
        preference,
        capital,
        "USD",
        alternatives,
        model,
        stable_hash((model.model_hash, asdict(preference), str(capital))),
    )


class GuidedRecommendationService:
    def __init__(
        self,
        universe: CurrentUniverseProvider,
        prices: BulkHistoryProvider,
        frontier: PortfolioFrontierService,
        *,
        cache: GuidedModelCache | None = None,
        clock: Callable[[], datetime] | None = None,
        configuration_key: str = "historical-v1",
    ) -> None:
        self._universe, self._prices, self._frontier = universe, prices, frontier
        self._cache, self._clock = cache, clock or (lambda: datetime.now(UTC))
        self._configuration_key = configuration_key

    def calculate(
        self,
        progress: Callable[[str], None],
        expected_return_estimator: EstimatorId = "historical_mean",
    ) -> GuidedModel:
        progress("loading_universe")
        try:
            universe = self._universe.get_current_universe()
        except ExternalDataUnavailableError as exc:
            raise data_unavailable(str(exc)) from exc
        benchmark = universe.universe.benchmark_asset_id
        assets = tuple(sorted({a.ticker for a in universe.assets} - {benchmark}))
        if not assets:
            raise data_unavailable("The current constituent universe is empty.")
        end = latest_completed_session_ceiling(self._clock())
        start = subtract_calendar_years(end, 3)
        progress("loading_prices")
        bulk = self._prices.get_bulk_history((*assets, benchmark), start, end)
        progress("checking_coverage")
        series = {s.asset_id: s for s in bulk.series}
        spy = series.get(benchmark)
        if spy is None or spy.currency is not Currency.USD:
            raise data_unavailable("The USD SPY benchmark is unavailable.")
        dates = tuple(o.observed_on for o in spy.observations if start <= o.observed_on <= end)
        if len(dates) < 253:
            raise invalid_input("INSUFFICIENT_HISTORY", "At least 253 SPY prices are required.")
        required = set(dates)
        excluded = {f.asset_id: f for f in bulk.failures if f.asset_id in assets}
        aligned: dict[str, tuple[Decimal, ...]] = {}
        for asset in (*assets, benchmark):
            item = series.get(asset)
            if item is None:
                excluded[asset] = HistoryFailure(asset, "Prices unavailable after one retry")
                continue
            observations = {o.observed_on: o.adjusted_close for o in item.observations}
            if item.currency is not Currency.USD or not required.issubset(observations):
                excluded[asset] = HistoryFailure(asset, "USD prices required on every SPY session")
                continue
            aligned[asset] = tuple(observations[d] for d in dates)
        eligible = tuple(a for a in assets if a in aligned)
        coverage = Coverage(
            len(assets), len(eligible), tuple(excluded[a] for a in sorted(excluded))
        )
        if len(eligible) * 10 < len(assets) * 9 or len(eligible) < 10:
            raise invalid_input(
                "INSUFFICIENT_COVERAGE",
                "At least 90% of constituents and ten eligible stocks are required.",
                coverage=asdict(coverage),
            )
        conventions = DEFAULT_FINANCIAL_CONVENTIONS
        content = stable_hash([(a, [str(v) for v in aligned[a]]) for a in (*eligible, benchmark)])
        provenance = DataProvenance(
            "bulk_yahoo_finance",
            self._clock(),
            content,
            any(p.stale_fallback for p in bulk.provenance),
        )
        history = PriceHistory(
            (*eligible, benchmark),
            tuple(series[a] for a in (*eligible, benchmark)),
            start,
            end,
            conventions.return_frequency,
            conventions.price_field,
            provenance,
        )
        key = stable_hash(
            (
                self._configuration_key,
                expected_return_estimator,
                self._frontier.configuration_signature,
                universe.provenance.content_hash,
                universe.universe.as_of_date,
                dates,
                content,
                asdict(coverage),
                asdict(conventions),
                0.1,
            )
        )
        cached = self._cache.get_model(key) if self._cache else None
        if cached:
            return replace(
                cached,
                price_sources=bulk.provenance,
                report=replace(
                    cached.report,
                    price_provenance=provenance,
                    universe_provenance=universe.provenance,
                ),
            )
        progress("calculating_alternatives")
        report = self._frontier.build_report(
            eligible,
            benchmark,
            dates,
            aligned,
            tuple((a, 0) for a in (*eligible, benchmark)),
            universe,
            history,
            OptimizationConstraints(0.1),
            expected_return_estimator=expected_return_estimator,
        )
        assumptions = tuple(a for a in report.assumptions if "timestamp-intersection" not in a)
        assumptions += (
            "Every eligible stock has USD adjusted-close prices on every observed SPY session; "
            "excluded constituents are listed and missing prices are never filled.",
            "The three-year history window estimates parameters; it is not an investment horizon.",
            "Conservative is relative within a stocks-only model, not capital protection.",
            "Capital scales illustrative USD amounts, not optimized weights; no share purchases "
            "are calculated. Cent rounding does not change model weights.",
        )
        report = replace(
            report,
            assumptions=assumptions,
            report_hash=stable_hash((report.report_hash, assumptions, key)),
        )
        model = GuidedModel(
            report, coverage, bulk.provenance, stable_hash((key, report.report_hash))
        )
        if self._cache:
            self._cache.put_model(key, model)
        return model
