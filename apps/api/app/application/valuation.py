"""Current-portfolio valuation use case and market-data alignment."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.application.errors import data_unavailable, invalid_input
from app.domain import (
    Currency,
    CurrentUniverseProvider,
    ExternalDataUnavailableError,
    MarketDataProvider,
    PortfolioValuationSnapshot,
    PriceField,
    PriceHistory,
    ReturnFrequency,
    ValuationLineItem,
)

NEW_YORK = ZoneInfo("America/New_York")


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper()
    if not ticker:
        raise invalid_input("INVALID_TICKER", "Ticker must be a non-empty string.")
    return ticker


def normalize_positions(
    positions: Sequence[tuple[str, Decimal]],
) -> tuple[tuple[str, Decimal], ...]:
    if not positions:
        raise invalid_input("EMPTY_PORTFOLIO", "At least one position is required.")
    normalized: list[tuple[str, Decimal]] = []
    for raw_ticker, quantity in positions:
        ticker = normalize_ticker(raw_ticker)
        if not quantity.is_finite() or quantity <= 0:
            raise invalid_input(
                "INVALID_QUANTITY",
                "Position quantities must be finite and positive.",
                ticker=ticker,
            )
        normalized.append((ticker, quantity))
    tickers = [ticker for ticker, _ in normalized]
    if len(set(tickers)) != len(tickers):
        raise invalid_input("DUPLICATE_TICKER", "Portfolio tickers must be unique.")
    normalized.sort(key=lambda item: item[0])
    return tuple(normalized)


def validate_supported_assets(
    requested_assets: tuple[str, ...], supported_assets: set[str]
) -> None:
    unsupported = [ticker for ticker in requested_assets if ticker not in supported_assets]
    if unsupported:
        raise invalid_input(
            "UNSUPPORTED_TICKER",
            "Every portfolio ticker must be a current S&P 500 constituent.",
            tickers=unsupported,
        )


def latest_completed_session_ceiling(now: datetime) -> date:
    local_now = now.astimezone(NEW_YORK)
    if local_now.timetz().replace(tzinfo=None) < time(16, 30):
        return local_now.date() - timedelta(days=1)
    return local_now.date()


def latest_common_prices(
    history: PriceHistory,
    requested_assets: tuple[str, ...],
    ceiling: date,
    *,
    maximum_staleness_days: int,
    maximum_consecutive_missing: int,
) -> tuple[date, dict[str, Decimal]]:
    by_asset = {item.asset_id: item for item in history.series}
    if tuple(history.asset_ids) != requested_assets:
        raise invalid_input(
            "PRICE_ASSET_ORDER_MISMATCH",
            "Price data does not preserve the requested asset ordering.",
        )
    if set(by_asset) != set(requested_assets) or len(by_asset) != len(history.series):
        raise invalid_input("MISSING_PRICE_SERIES", "Price data is missing one or more assets.")

    date_sets: dict[str, set[date]] = {}
    observations: dict[str, dict[date, Decimal]] = {}
    for asset_id in requested_assets:
        series = by_asset[asset_id]
        if series.currency is not Currency.USD:
            raise invalid_input(
                "INCOMPATIBLE_CURRENCY",
                "All price data must be denominated in USD.",
                ticker=asset_id,
            )
        eligible = {
            item.observed_on: item.adjusted_close
            for item in series.observations
            if item.observed_on <= ceiling
        }
        if not eligible:
            raise invalid_input(
                "MISSING_PRICE_SERIES",
                "No eligible adjusted-close price is available.",
                ticker=asset_id,
            )
        observations[asset_id] = eligible
        date_sets[asset_id] = set(eligible)

    union_dates = sorted(set().union(*date_sets.values()))
    for asset_id, available in date_sets.items():
        run = longest_missing_run(union_dates, available)
        if run > maximum_consecutive_missing:
            raise invalid_input(
                "MATERIAL_PRICE_GAP",
                "A price series contains a material missing-data gap.",
                ticker=asset_id,
                consecutive_missing_observations=run,
            )

    common_dates = set.intersection(*date_sets.values())
    if not common_dates:
        raise invalid_input("INSUFFICIENT_ALIGNED_DATA", "No common valuation date exists.")
    valued_on = max(common_dates)
    age = (ceiling - valued_on).days
    if age > maximum_staleness_days:
        raise invalid_input(
            "STALE_VALUATION_DATA",
            "The newest common adjusted close is too old for valuation.",
            valued_on=valued_on.isoformat(),
            maximum_staleness_days=maximum_staleness_days,
        )
    return valued_on, {asset_id: observations[asset_id][valued_on] for asset_id in requested_assets}


def longest_missing_run(expected: Sequence[date], available: set[date]) -> int:
    longest = current = 0
    for observed_on in expected:
        if observed_on in available:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


class PortfolioValuationService:
    def __init__(
        self,
        universe_provider: CurrentUniverseProvider,
        market_data_provider: MarketDataProvider,
        *,
        clock: Callable[[], datetime] | None = None,
        maximum_staleness_days: int = 7,
        maximum_consecutive_missing: int = 5,
    ) -> None:
        self._universe_provider = universe_provider
        self._market_data_provider = market_data_provider
        self._clock = clock or (lambda: datetime.now(UTC))
        self._maximum_staleness_days = maximum_staleness_days
        self._maximum_consecutive_missing = maximum_consecutive_missing

    def value(
        self, positions: Sequence[tuple[str, Decimal]], as_of: date | None = None
    ) -> PortfolioValuationSnapshot:
        now = self._clock()
        ceiling = as_of or latest_completed_session_ceiling(now)
        if ceiling > now.astimezone(NEW_YORK).date():
            raise invalid_input("INVALID_AS_OF", "The as-of date cannot be in the future.")

        normalized = normalize_positions(positions)
        requested_assets = tuple(ticker for ticker, _ in normalized)

        try:
            universe_snapshot = self._universe_provider.get_current_universe()
        except ExternalDataUnavailableError as exc:
            raise data_unavailable(str(exc), source="wikipedia") from exc
        validate_supported_assets(
            requested_assets, {asset.ticker for asset in universe_snapshot.assets}
        )

        start = ceiling - timedelta(days=self._maximum_staleness_days + 3)
        try:
            history = self._market_data_provider.get_price_history(
                requested_assets,
                start,
                ceiling,
                ReturnFrequency.DAILY,
                PriceField.ADJUSTED_CLOSE,
                refresh_if_stale=as_of is None,
            )
        except ExternalDataUnavailableError as exc:
            raise data_unavailable(str(exc), source="yahoo_finance") from exc
        valued_on, prices = latest_common_prices(
            history,
            requested_assets,
            ceiling,
            maximum_staleness_days=self._maximum_staleness_days,
            maximum_consecutive_missing=self._maximum_consecutive_missing,
        )
        values = {ticker: prices[ticker] * quantity for ticker, quantity in normalized}
        total = sum(values.values(), Decimal(0))
        lines = tuple(
            ValuationLineItem(
                ticker=ticker,
                quantity=quantity,
                unit_price=prices[ticker],
                market_value=values[ticker],
                weight=values[ticker] / total,
            )
            for ticker, quantity in normalized
        )
        assumptions = (
            "USD base currency",
            "Daily adjusted-close prices",
            "No missing-value imputation; assets aligned by timestamp intersection",
            "Current S&P 500 membership is used, including for historical as-of dates",
            "S&P 500 membership is not historically reconstructed (survivorship bias applies)",
        )
        stable = {
            "valued_on": valued_on.isoformat(),
            "universe_hash": universe_snapshot.provenance.content_hash,
            "price_hash": history.provenance.content_hash,
            "positions": [
                [line.ticker, str(line.quantity), str(line.unit_price), str(line.market_value)]
                for line in lines
            ],
            "assumptions": assumptions,
        }
        snapshot_hash = hashlib.sha256(
            json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return PortfolioValuationSnapshot(
            requested_as_of=as_of,
            valued_on=valued_on,
            currency=Currency.USD,
            positions=lines,
            total_market_value=total,
            universe_as_of=universe_snapshot.universe.as_of_date,
            universe_provenance=universe_snapshot.provenance,
            price_provenance=history.provenance,
            snapshot_hash=snapshot_hash,
            assumptions=assumptions,
        )
