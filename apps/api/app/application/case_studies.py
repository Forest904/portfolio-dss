"""Reproducible decision-support cases built only from a frozen snapshot."""

from __future__ import annotations

import html
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Annotated, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.analysis import align_price_history
from app.application.backtest import FrozenSnapshot, canonical_json
from app.application.frontier import FrontierReport, PortfolioFrontierService
from app.domain import (
    Asset,
    AssetPriceSeries,
    Currency,
    DataProvenance,
    HistoricalMeanEstimator,
    HistoricalSampleRiskEstimator,
    InvestmentUniverse,
    OptimizationConstraints,
    PriceField,
    PriceHistory,
    PriceObservation,
    ReturnFrequency,
    UniverseSnapshot,
)
from app.domain.frontier import EfficientFrontierGenerator
from app.domain.simulation import (
    SimulationConfiguration,
    SimulationEngine,
    SimulationMetadata,
    SimulationPortfolio,
    SimulationRequest,
    SimulationResult,
)


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ExistingPortfolioCase(BoundaryModel):
    kind: Literal["existing_portfolio"]
    id: str
    title: str
    target_weights: dict[str, float]
    expected_return_estimator: Literal["historical_mean", "simple_forecast"] = "historical_mean"
    max_weight: float | None = None

    @model_validator(mode="after")
    def valid_weights(self) -> ExistingPortfolioCase:
        if not self.target_weights or abs(sum(self.target_weights.values()) - 1) > 1e-9:
            raise ValueError("target weights must sum to one")
        if any(not 0 < weight <= 1 for weight in self.target_weights.values()):
            raise ValueError("target weights must be positive fractions")
        return self


class GuidedProfileCase(BoundaryModel):
    kind: Literal["guided_profiles"]
    id: str
    title: str
    tickers: tuple[str, ...]
    capital: Decimal
    expected_return_estimator: Literal["historical_mean", "simple_forecast"] = "historical_mean"
    max_weight: float | None = 0.4

    @model_validator(mode="after")
    def valid_case(self) -> GuidedProfileCase:
        if self.capital <= 0 or not self.tickers or len(set(self.tickers)) != len(self.tickers):
            raise ValueError("guided capital must be positive and tickers unique")
        if any(not ticker.strip() or ticker != ticker.strip().upper() for ticker in self.tickers):
            raise ValueError("tickers must be trimmed and uppercase")
        return self


class EstimatorComparisonCase(BoundaryModel):
    kind: Literal["estimator_comparison"]
    id: str
    title: str
    tickers: tuple[str, ...]
    capital: Decimal
    max_weight: float | None = 0.4

    @model_validator(mode="after")
    def valid_case(self) -> EstimatorComparisonCase:
        if self.capital <= 0 or not self.tickers or len(set(self.tickers)) != len(self.tickers):
            raise ValueError("comparison capital must be positive and tickers unique")
        if any(not ticker.strip() or ticker != ticker.strip().upper() for ticker in self.tickers):
            raise ValueError("tickers must be trimmed and uppercase")
        return self


CaseDefinition = Annotated[
    ExistingPortfolioCase | GuidedProfileCase | EstimatorComparisonCase,
    Field(discriminator="kind"),
]


class CaseStudyManifest(BoundaryModel):
    version: Literal["case-studies-v1"] = "case-studies-v1"
    analysis_start: date
    analysis_end: date
    simulation: SimulationConfiguration = SimulationConfiguration(3, 10_000, 42)
    cases: tuple[CaseDefinition, ...]

    @model_validator(mode="after")
    def valid_manifest(self) -> CaseStudyManifest:
        if self.analysis_start >= self.analysis_end:
            raise ValueError("analysis_start must precede analysis_end")
        if (
            not self.cases
            or any(not case.id.strip() for case in self.cases)
            or len({case.id for case in self.cases}) != len(self.cases)
        ):
            raise ValueError("case IDs must be non-empty and unique")
        return self


class FrozenProviders:
    """Market/universe ports over a validated, immutable snapshot."""

    def __init__(self, snapshot: FrozenSnapshot) -> None:
        if snapshot.snapshot_hash != snapshot.payload_hash():
            raise ValueError("snapshot content hash mismatch")
        self.snapshot = snapshot
        constituents = tuple(
            Asset(
                item.ticker,
                item.ticker,
                item.name,
                item.exchange,
                Currency.USD,
                item.sector,
                "Frozen case-study constituent",
                frozenset({"sp500"}),
            )
            for item in snapshot.constituents
        )
        self.universe = UniverseSnapshot(
            InvestmentUniverse(
                "sp500",
                "Selected frozen S&P 500 demonstration subset",
                snapshot.universe_as_of,
                tuple(item.id for item in constituents),
                "SPY",
                "SPDR S&P 500 ETF Trust (total-return proxy)",
            ),
            constituents,
            DataProvenance(**snapshot.universe_provenance.model_dump()),
        )

    def get_current_universe(self, *, refresh_if_stale: bool = True) -> UniverseSnapshot:
        return self.universe

    def get_price_history(
        self,
        asset_ids: Sequence[str],
        start: date,
        end: date,
        frequency: ReturnFrequency,
        price_field: PriceField,
        *,
        refresh_if_stale: bool = True,
    ) -> PriceHistory:
        if frequency is not ReturnFrequency.DAILY or price_field is not PriceField.ADJUSTED_CLOSE:
            raise ValueError("frozen case studies support daily adjusted close only")
        indexes = [
            index for index, value in enumerate(self.snapshot.dates) if start <= value <= end
        ]
        ordered = tuple(asset_ids)
        if not indexes or any(asset not in self.snapshot.asset_ids for asset in ordered):
            raise ValueError("snapshot does not cover the requested case")
        rows = dict(zip(self.snapshot.asset_ids, self.snapshot.adjusted_close, strict=True))
        series = tuple(
            AssetPriceSeries(
                asset,
                Currency.USD,
                tuple(
                    PriceObservation(self.snapshot.dates[index], rows[asset][index])
                    for index in indexes
                ),
            )
            for asset in ordered
        )
        provisional = PriceHistory(
            ordered,
            series,
            start,
            end,
            frequency,
            price_field,
            DataProvenance(
                "frozen_snapshot", self.snapshot.price_provenance.retrieved_at, "pending"
            ),
        )
        return PriceHistory(
            ordered,
            series,
            start,
            end,
            frequency,
            price_field,
            DataProvenance(
                "frozen_snapshot",
                self.snapshot.price_provenance.retrieved_at,
                provisional.calculate_content_hash(),
            ),
        )


def _service(
    providers: FrozenProviders, end: date, generator: EfficientFrontierGenerator
) -> PortfolioFrontierService:
    return PortfolioFrontierService(
        providers,
        providers,
        HistoricalMeanEstimator(),
        HistoricalSampleRiskEstimator(),
        generator,
        clock=lambda: datetime.combine(end, time(12), UTC),
    )


def _guided_report(
    service: PortfolioFrontierService,
    providers: FrozenProviders,
    tickers: tuple[str, ...],
    start: date,
    end: date,
    max_weight: float | None,
    estimator: Literal["historical_mean", "simple_forecast"],
) -> FrontierReport:
    history = providers.get_price_history(
        (*tickers, "SPY"), start, end, ReturnFrequency.DAILY, PriceField.ADJUSTED_CLOSE
    )
    dates, aligned, excluded = align_price_history(
        history, (*tickers, "SPY"), maximum_consecutive_missing=0
    )
    return service.build_report(
        tickers,
        "SPY",
        dates,
        aligned,
        excluded,
        providers.universe,
        history,
        OptimizationConstraints(max_weight),
        expected_return_estimator=estimator,
    )


def _moderate_simulation(
    report: FrontierReport,
    capital: Decimal,
    config: SimulationConfiguration,
    engine: SimulationEngine,
) -> SimulationResult:
    profile = next(item for item in report.frontier.profiles if item.name == "moderate")
    point = next(item for item in report.frontier.points if item.id == profile.point_id)
    metadata = SimulationMetadata(
        report.expected_return_model.estimation_start,
        report.expected_return_model.estimation_end,
        report.expected_return_model.observations,
        report.expected_return_model.estimator_name,
        report.risk_model.estimator_name,
    )
    request = SimulationRequest(
        (
            SimulationPortfolio(
                "moderate", point.metrics.expected_return, point.metrics.variance, metadata
            ),
        ),
        float(capital),
        report.report_hash,
        config,
    )
    return engine.simulate(request)


def generate_case_studies(
    manifest: CaseStudyManifest,
    snapshot: FrozenSnapshot,
    frontier_generator: EfficientFrontierGenerator,
    simulation_engine: SimulationEngine,
) -> dict[str, object]:
    providers = FrozenProviders(snapshot)
    service = _service(providers, manifest.analysis_end, frontier_generator)
    results: list[dict[str, object]] = []
    for case in manifest.cases:
        if isinstance(case, ExistingPortfolioCase):
            history = providers.get_price_history(
                tuple(case.target_weights),
                manifest.analysis_start,
                manifest.analysis_end,
                ReturnFrequency.DAILY,
                PriceField.ADJUSTED_CLOSE,
            )
            last = {item.asset_id: item.observations[-1].adjusted_close for item in history.series}
            positions = tuple(
                (ticker, Decimal("10000") * Decimal(str(weight)) / last[ticker])
                for ticker, weight in case.target_weights.items()
            )
            report = service.generate(
                positions,
                start=manifest.analysis_start,
                end=manifest.analysis_end,
                max_weight=case.max_weight,
                expected_return_estimator=case.expected_return_estimator,
            )
            results.append({"definition": case.model_dump(mode="json"), "frontier": asdict(report)})
        elif isinstance(case, GuidedProfileCase):
            report = _guided_report(
                service,
                providers,
                case.tickers,
                manifest.analysis_start,
                manifest.analysis_end,
                case.max_weight,
                case.expected_return_estimator,
            )
            results.append(
                {
                    "definition": case.model_dump(mode="json"),
                    "frontier": asdict(report),
                    "simulation": asdict(
                        _moderate_simulation(
                            report, case.capital, manifest.simulation, simulation_engine
                        )
                    ),
                }
            )
        else:
            reports = {
                estimator: _guided_report(
                    service,
                    providers,
                    case.tickers,
                    manifest.analysis_start,
                    manifest.analysis_end,
                    case.max_weight,
                    estimator,
                )
                for estimator in cast(
                    tuple[Literal["historical_mean", "simple_forecast"], ...],
                    ("historical_mean", "simple_forecast"),
                )
            }
            results.append(
                {
                    "definition": case.model_dump(mode="json"),
                    "frontiers": {name: asdict(report) for name, report in reports.items()},
                    "simulations": {
                        name: asdict(
                            _moderate_simulation(
                                report, case.capital, manifest.simulation, simulation_engine
                            )
                        )
                        for name, report in reports.items()
                    },
                }
            )
    payload: dict[str, object] = {
        "version": manifest.version,
        "snapshot_hash": snapshot.snapshot_hash,
        "analysis_window": [manifest.analysis_start, manifest.analysis_end],
        "limitations": [
            "These selected cases are educational examples, not investment advice.",
            "The five-stock basket is not the full S&P 500 and introduces selection bias.",
            "Current membership and revised adjusted-close data introduce survivorship "
            "and revision bias.",
            "Expected returns, covariance estimates, and simulations are uncertain "
            "and not guarantees.",
            "Costs, taxes, turnover, slippage, and integer-share execution are not modeled.",
        ],
        "cases": results,
    }
    payload["report_hash"] = (
        __import__("hashlib").sha256(canonical_json(payload).encode()).hexdigest()
    )
    return payload


def render_case_studies_html(payload: dict[str, object]) -> str:
    cases = cast(list[dict[str, Any]], payload["cases"])
    sections: list[str] = []
    for item in cases:
        definition = item["definition"]
        title = html.escape(str(definition["title"]))
        kind = html.escape(str(definition["kind"]).replace("_", " "))
        reports = cast(
            dict[str, dict[str, Any]],
            item.get("frontiers", {"selected": item.get("frontier")}),
        )
        cards: list[str] = []
        for name, raw in reports.items():
            profiles = raw["frontier"]["profiles"]
            points = {point["id"]: point for point in raw["frontier"]["points"]}
            rows = "".join(
                "<tr><th>"
                + html.escape(profile["name"])
                + "</th><td>"
                + f"{100 * points[profile['point_id']]['metrics']['expected_return']:.2f}%</td><td>"
                + f"{100 * points[profile['point_id']]['metrics']['volatility']:.2f}%</td></tr>"
                for profile in profiles
            )
            cards.append(
                f"<h3>{html.escape(name.replace('_', ' ').title())}</h3>"
                "<table><thead><tr><th>Profile</th><th>Estimated annual return</th>"
                f"<th>Estimated annual volatility</th></tr></thead><tbody>{rows}</tbody></table>"
            )
        sections.append(f"<section><p>{kind}</p><h2>{title}</h2>{''.join(cards)}</section>")
    limitations = "".join(
        f"<li>{html.escape(str(value))}</li>"
        for value in cast(list[object], payload["limitations"])
    )
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'><link rel='icon' href='data:,'>"
        "<meta name='viewport' "
        "content='width=device-width'><title>Portfolio DSS case studies</title><style>"
        "body{font:16px system-ui;max-width:980px;margin:auto;padding:2rem;color:#17211b}"
        "section{border:1px solid #ccd7d0;border-radius:12px;padding:1rem;margin:1rem 0}"
        "table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.5rem;"
        "border-bottom:1px solid #ddd}small{overflow-wrap:anywhere}</style><main>"
        "<h1>Portfolio DSS — reproducible case studies</h1>"
        "<p>Observed history, model estimates, and simulated outcomes are labelled separately.</p>"
        + "".join(sections)
        + f"<section><h2>Limitations</h2><ul>{limitations}</ul></section>"
        + f"<small>Report hash: {html.escape(str(payload['report_hash']))}</small>"
        "</main></html>"
    )
