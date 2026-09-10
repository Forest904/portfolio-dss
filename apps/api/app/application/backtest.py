"""Snapshot acquisition, validation and composition for offline backtest replay."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt

from app.application.estimators import FORECAST_VERSION, HISTORICAL_VERSION
from app.domain.backtest import (
    BacktestConfig,
    BacktestEngine,
    BacktestPrices,
    BacktestReport,
    EstimatorStrategy,
    WindowMode,
)
from app.domain.catalog import CurrentUniverseProvider
from app.domain.conventions import DEFAULT_FINANCIAL_CONVENTIONS, PriceField, ReturnFrequency
from app.domain.errors import DomainValidationError
from app.domain.forecast import HALF_LIFE, SimpleForecastEstimator
from app.domain.market_data import DataProvenance, MarketDataProvider, PriceHistory
from app.domain.models import Currency
from app.domain.optimization import (
    HistoricalMeanEstimator,
    HistoricalSampleRiskEstimator,
    PortfolioOptimizer,
)


def _json_default(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Decimal, Enum)):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        default=_json_default,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class BacktestSettings(BoundaryModel):
    tickers: tuple[str, ...] = ("AAPL", "MSFT", "JPM", "JNJ", "XOM")
    # 2018 alone has fewer than the 253 prices required before the first 2019 execution.
    history_start: date = date(2017, 12, 28)
    history_end: date = date(2025, 12, 31)
    evaluation_start: date = date(2019, 1, 1)
    evaluation_end: date = date(2025, 12, 31)
    window_modes: tuple[WindowMode, ...] = ("rolling", "expanding")
    training_returns: StrictInt = 252
    rebalance_sessions: StrictInt = 21
    initial_capital: StrictFloat = 10_000.0
    risk_aversion: StrictFloat = 3.0
    max_weight: StrictFloat | None = 0.4

    def to_domain(self) -> BacktestConfig:
        return BacktestConfig(**self.model_dump())


class ProvenanceRecord(BoundaryModel):
    provider: str
    retrieved_at: datetime
    content_hash: str
    stale_fallback: bool

    def validate_domain(self) -> None:
        DataProvenance(**self.model_dump())


class ConstituentRecord(BoundaryModel):
    ticker: str
    name: str
    sector: str
    exchange: str
    currency: Literal["USD"] = "USD"


class FrozenSnapshot(BoundaryModel):
    version: Literal["backtest-snapshot-v1"] = "backtest-snapshot-v1"
    history_start: date
    history_end: date
    asset_ids: tuple[str, ...]
    dates: tuple[date, ...]
    adjusted_close: tuple[tuple[Decimal, ...], ...]
    currency: Literal["USD"] = "USD"
    price_field: Literal["adjusted_close"] = "adjusted_close"
    frequency: Literal["daily"] = "daily"
    calendar: Literal["SPY observations"] = "SPY observations"
    constituents: tuple[ConstituentRecord, ...]
    universe_as_of: date
    universe_provenance: ProvenanceRecord
    price_provenance: ProvenanceRecord
    snapshot_hash: str

    def payload_hash(self) -> str:
        return content_hash(self.model_dump(mode="json", exclude={"snapshot_hash"}))

    def validate_for(self, config: BacktestConfig) -> BacktestPrices:
        if self.snapshot_hash != self.payload_hash():
            raise DomainValidationError("snapshot content hash mismatch")
        self.universe_provenance.validate_domain()
        self.price_provenance.validate_domain()
        if self.history_start > config.history_start or self.history_end < config.history_end:
            raise DomainValidationError("snapshot does not cover configured history bounds")
        if self.asset_ids != (*config.tickers, "SPY"):
            raise DomainValidationError("snapshot basket/order differs from configuration")
        if tuple(c.ticker for c in self.constituents) != config.tickers:
            raise DomainValidationError("snapshot constituent metadata differs from basket")
        if (
            not self.dates
            or self.dates[0] < self.history_start
            or self.dates[-1] > self.history_end
        ):
            raise DomainValidationError("snapshot dates lie outside declared bounds")
        # Validate the entire snapshot before slicing so malformed extra data is never ignored.
        validated = BacktestPrices(
            self.asset_ids,
            self.dates,
            tuple(tuple(float(p) for p in row) for row in self.adjusted_close),
        )
        indexes = [
            i for i, d in enumerate(self.dates) if config.history_start <= d <= config.history_end
        ]
        return BacktestPrices(
            validated.asset_ids,
            tuple(self.dates[i] for i in indexes),
            tuple(tuple(row[i] for i in indexes) for row in validated.adjusted_close),
        )


def strict_prices(
    history: PriceHistory, config: BacktestConfig
) -> tuple[
    tuple[date, ...],
    tuple[tuple[Decimal, ...], ...],
]:
    expected = (*config.tickers, "SPY")
    if history.asset_ids != expected or tuple(s.asset_id for s in history.series) != expected:
        raise DomainValidationError("provider price assets/order differ from requested basket")
    if (
        history.frequency != ReturnFrequency.DAILY
        or history.price_field != PriceField.ADJUSTED_CLOSE
    ):
        raise DomainValidationError("daily adjusted-close prices are required")
    if history.start != config.history_start or history.end != config.history_end:
        raise DomainValidationError("provider history bounds differ from request")
    by_asset = {
        s.asset_id: {p.observed_on: p.adjusted_close for p in s.observations}
        for s in history.series
    }
    dates = tuple(by_asset["SPY"])
    if not dates:
        raise DomainValidationError("SPY has no session observations")
    for series in history.series:
        if series.currency != Currency.USD:
            raise DomainValidationError(f"{series.asset_id}: USD prices required")
        missing = set(dates) - by_asset[series.asset_id].keys()
        extra = by_asset[series.asset_id].keys() - set(dates)
        if missing or extra:
            raise DomainValidationError(
                f"{series.asset_id}: session mismatch; "
                f"missing={sorted(missing)}, extra={sorted(extra)}"
            )
    rows = tuple(tuple(by_asset[a][d] for d in dates) for a in expected)
    BacktestPrices(expected, dates, tuple(tuple(float(p) for p in row) for row in rows))
    return dates, rows


def acquire_snapshot(
    config: BacktestConfig,
    provider: MarketDataProvider,
    universe: CurrentUniverseProvider,
) -> FrozenSnapshot:
    membership = universe.get_current_universe(refresh_if_stale=True)
    assets = {a.ticker: a for a in membership.assets}
    unknown = set(config.tickers) - assets.keys()
    if unknown:
        raise DomainValidationError(f"not in frozen current S&P 500 membership: {sorted(unknown)}")
    history = provider.get_price_history(
        (*config.tickers, "SPY"),
        config.history_start,
        config.history_end,
        ReturnFrequency.DAILY,
        PriceField.ADJUSTED_CLOSE,
        refresh_if_stale=False,
    )
    if history.provenance.content_hash != history.calculate_content_hash():
        raise DomainValidationError("provider content hash mismatch")
    dates, rows = strict_prices(history, config)
    snapshot = FrozenSnapshot(
        history_start=history.start,
        history_end=history.end,
        asset_ids=history.asset_ids,
        dates=dates,
        adjusted_close=rows,
        constituents=tuple(
            ConstituentRecord(
                ticker=a.ticker,
                name=a.name,
                sector=a.sector,
                exchange=a.exchange,
            )
            for a in (assets[t] for t in config.tickers)
        ),
        universe_as_of=membership.universe.as_of_date,
        universe_provenance=ProvenanceRecord(**asdict(membership.provenance)),
        price_provenance=ProvenanceRecord(**asdict(history.provenance)),
        snapshot_hash="",
    )
    snapshot = snapshot.model_copy(update={"snapshot_hash": snapshot.payload_hash()})
    snapshot.validate_for(config)
    return snapshot


def build_engine(optimizer: PortfolioOptimizer, solver_identity: str) -> BacktestEngine:
    risk = HistoricalSampleRiskEstimator()
    return BacktestEngine(
        (
            EstimatorStrategy(
                "historical_mean",
                f"{HISTORICAL_VERSION}; historical-sample-covariance-v1; {solver_identity}",
                HistoricalMeanEstimator(),
                risk,
                optimizer,
            ),
            EstimatorStrategy(
                "simple_forecast",
                f"{FORECAST_VERSION}; half-life={HALF_LIFE}; "
                f"historical-sample-covariance-v1; {solver_identity}",
                SimpleForecastEstimator(),
                risk,
                optimizer,
            ),
        )
    )


ASSUMPTIONS = (
    "Realized historical backtest outcomes under hypothetical allocations, "
    "not forecasts or guarantees.",
    "Fixed basket selected using current membership: selection and survivorship bias apply; "
    "historical membership and delistings are not reconstructed.",
    "Adjusted-close data may be revised; "
    "frozen data is not a point-in-time historical data vintage.",
    "Train through the prior session, execute at the next adjusted close, earn returns thereafter.",
    "Idealized close execution with fractional allocations and reinvested adjusted-price returns; "
    "no costs, slippage, taxes, leverage, or turnover constraints.",
    "Weights drift between rebalances; the weight cap applies only at optimized rebalances.",
    "Equal weight is periodically rebalanced; "
    "SPY is an S&P 500 ETF total-return proxy held throughout.",
    "SPY observation dates define sessions; complete basket coverage is mandatory with no filling "
    "or dropped dates. Missing dates shared by all series cannot be detected "
    "without an external calendar.",
    "Annualized realized return is geometric (252 sessions/year); "
    "estimated model means are arithmetic.",
    "Settings are fixed demonstration choices, not tuned on evaluation results; "
    "no superiority claim.",
)


def report_payload(
    report: BacktestReport,
    snapshot: FrozenSnapshot,
    runtime: dict[str, str],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "report": asdict(report),
        "snapshot_hash": snapshot.snapshot_hash,
        "price_provenance": snapshot.price_provenance.model_dump(mode="json"),
        "universe_provenance": snapshot.universe_provenance.model_dump(mode="json"),
        "universe_as_of": snapshot.universe_as_of,
        "constituents": [c.model_dump() for c in snapshot.constituents],
        "runtime": runtime,
        "assumptions": ASSUMPTIONS,
        "conventions": asdict(DEFAULT_FINANCIAL_CONVENTIONS),
    }
    payload["report_hash"] = content_hash(payload)
    return payload
