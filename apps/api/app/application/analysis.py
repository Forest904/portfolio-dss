"""Historical portfolio analysis orchestration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from app.application.errors import data_unavailable, invalid_input
from app.application.valuation import (
    NEW_YORK,
    latest_completed_session_ceiling,
    longest_missing_run,
    normalize_positions,
    validate_supported_assets,
)
from app.domain import (
    DEFAULT_FINANCIAL_CONVENTIONS,
    AnalysisValuation,
    AnalysisValuationPosition,
    AnalysisWindow,
    Currency,
    CurrentUniverseProvider,
    ExternalDataUnavailableError,
    MarketDataProvider,
    PortfolioAnalysisReport,
    PriceField,
    PriceHistory,
    ReturnFrequency,
    calculate_historical_analytics,
)

MINIMUM_ALIGNED_PRICES = 253


def subtract_calendar_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def align_price_history(
    history: PriceHistory,
    requested_assets: tuple[str, ...],
    *,
    maximum_consecutive_missing: int,
    minimum_observations: int = MINIMUM_ALIGNED_PRICES,
) -> tuple[tuple[date, ...], dict[str, tuple[Decimal, ...]], tuple[tuple[str, int], ...]]:
    if tuple(history.asset_ids) != requested_assets:
        raise invalid_input(
            "PRICE_ASSET_ORDER_MISMATCH",
            "Price data does not preserve the requested asset ordering.",
        )
    by_asset = {item.asset_id: item for item in history.series}
    if set(by_asset) != set(requested_assets) or len(by_asset) != len(history.series):
        raise invalid_input("MISSING_PRICE_SERIES", "Price data is missing one or more assets.")

    observations: dict[str, dict[date, Decimal]] = {}
    date_sets: dict[str, set[date]] = {}
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
            if history.start <= item.observed_on <= history.end
        }
        if not eligible:
            raise invalid_input(
                "MISSING_PRICE_SERIES",
                "No adjusted-close prices are available in the requested history window.",
                ticker=asset_id,
            )
        observations[asset_id] = eligible
        date_sets[asset_id] = set(eligible)

    union_dates = sorted(set().union(*date_sets.values()))
    excluded: list[tuple[str, int]] = []
    for asset_id in requested_assets:
        available = date_sets[asset_id]
        run = longest_missing_run(union_dates, available)
        if run > maximum_consecutive_missing:
            raise invalid_input(
                "MATERIAL_PRICE_GAP",
                "A price series contains a material missing-data gap.",
                ticker=asset_id,
                consecutive_missing_observations=run,
            )
        excluded.append((asset_id, len(union_dates) - len(available)))

    common_dates = tuple(sorted(set.intersection(*date_sets.values())))
    if len(common_dates) < minimum_observations:
        raise invalid_input(
            "INSUFFICIENT_HISTORY",
            "Not enough aligned history is available for analysis.",
            required_price_observations=minimum_observations,
            required_return_observations=minimum_observations - 1,
            available_price_observations=len(common_dates),
            available_return_observations=max(0, len(common_dates) - 1),
        )
    aligned = {
        asset_id: tuple(observations[asset_id][observed_on] for observed_on in common_dates)
        for asset_id in requested_assets
    }
    return common_dates, aligned, tuple(excluded)


class PortfolioAnalysisService:
    def __init__(
        self,
        universe_provider: CurrentUniverseProvider,
        market_data_provider: MarketDataProvider,
        *,
        clock: Callable[[], datetime] | None = None,
        maximum_consecutive_missing: int = 5,
    ) -> None:
        self._universe_provider = universe_provider
        self._market_data_provider = market_data_provider
        self._clock = clock or (lambda: datetime.now(UTC))
        self._maximum_consecutive_missing = maximum_consecutive_missing

    def analyze(
        self,
        positions: Sequence[tuple[str, Decimal]],
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> PortfolioAnalysisReport:
        normalized = normalize_positions(positions)
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
        asset_by_ticker = {asset.ticker: asset for asset in universe_snapshot.assets}
        asset_ids = tuple(ticker for ticker, _ in normalized)
        validate_supported_assets(asset_ids, set(asset_by_ticker))
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
        quantities = tuple(float(quantity) for _, quantity in normalized)
        sectors = tuple(asset_by_ticker[asset_id].sector for asset_id in asset_ids)
        analytics = calculate_historical_analytics(
            asset_ids=asset_ids,
            benchmark_asset_id=benchmark_id,
            dates=dates,
            prices={
                asset_id: tuple(float(value) for value in values)
                for asset_id, values in aligned.items()
            },
            quantities=quantities,
            sectors=sectors,
            annualization_periods=DEFAULT_FINANCIAL_CONVENTIONS.annualization_periods,
        )

        ending_prices = {asset_id: aligned[asset_id][-1] for asset_id in asset_ids}
        market_values = {
            ticker: quantity * ending_prices[ticker] for ticker, quantity in normalized
        }
        total_value = sum(market_values.values(), Decimal(0))
        valuation_positions = tuple(
            AnalysisValuationPosition(
                ticker=ticker,
                quantity=quantity,
                unit_price=ending_prices[ticker],
                market_value=market_values[ticker],
                weight=market_values[ticker] / total_value,
                sector=asset_by_ticker[ticker].sector,
            )
            for ticker, quantity in normalized
        )
        diagnostics = tuple(
            [
                "Undefined correlations for zero-variance assets: "
                f"{', '.join(analytics.undefined_correlation_assets)}."
            ]
            if analytics.undefined_correlation_assets
            else []
        )
        assumptions = (
            "Observed historical results; not forecasts or guaranteed future performance",
            "USD daily adjusted-close prices and simple returns",
            "252 trading periods per year; return is geometric CAGR and volatility is "
            "sample volatility",
            "No missing-value imputation; all holdings and SPY use timestamp-intersection "
            "alignment",
            "Current positions and the equal-weight alternative are buy-and-hold with no "
            "rebalancing or costs",
            "SPY is an ETF total-return proxy for the S&P 500, not the official index",
            "Current S&P 500 membership and sector classifications are used "
            "(survivorship bias applies)",
        )
        stable = {
            "positions": [[ticker, str(quantity)] for ticker, quantity in normalized],
            "requested_window": [requested_start.isoformat(), requested_end.isoformat()],
            "effective_window": [dates[0].isoformat(), dates[-1].isoformat()],
            "universe_hash": universe_snapshot.provenance.content_hash,
            "price_hash": history.provenance.content_hash,
            "assumptions": assumptions,
        }
        analysis_hash = hashlib.sha256(
            json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return PortfolioAnalysisReport(
            valuation=AnalysisValuation(
                valued_on=dates[-1],
                currency=Currency.USD,
                total_market_value=total_value,
                positions=valuation_positions,
            ),
            window=AnalysisWindow(
                requested_start=requested_start,
                requested_end=requested_end,
                effective_start=dates[0],
                effective_end=dates[-1],
                aligned_price_observations=len(dates),
                return_observations=len(dates) - 1,
                excluded_observations=excluded,
            ),
            analytics=analytics,
            universe_as_of=universe_snapshot.universe.as_of_date,
            universe_provenance=universe_snapshot.provenance,
            price_provenance=history.provenance,
            assumptions=assumptions,
            diagnostics=diagnostics,
            analysis_hash=analysis_hash,
        )
