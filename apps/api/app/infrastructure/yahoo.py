"""Yahoo Finance adjusted-close adapter with persistent read-through caching."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
import yfinance as yf  # type: ignore[import-untyped]

from app.domain import (
    AssetPriceSeries,
    Currency,
    DataProvenance,
    ExternalDataUnavailableError,
    PriceField,
    PriceHistory,
    PriceObservation,
    ReturnFrequency,
)
from app.infrastructure.cache import PriceCacheEntry, SQLiteCache


def yahoo_symbol(asset_id: str) -> str:
    return asset_id.replace(".", "-")


class YahooFinanceMarketDataProvider:
    provider_id = "yahoo_finance"

    def __init__(
        self,
        cache: SQLiteCache,
        *,
        timeout_seconds: float = 15.0,
        refresh_ttl: timedelta = timedelta(hours=6),
        stale_fallback_limit: timedelta = timedelta(days=7),
        clock: Callable[[], datetime] | None = None,
        downloader: Callable[..., Any] | None = None,
    ) -> None:
        self._cache = cache
        self._timeout_seconds = timeout_seconds
        self._refresh_ttl = refresh_ttl
        self._stale_fallback_limit = stale_fallback_limit
        self._clock = clock or (lambda: datetime.now(UTC))
        self._downloader = downloader or yf.download

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
        ordered = tuple(asset_ids)
        now = self._clock()
        components: dict[str, tuple[AssetPriceSeries, datetime, bool]] = {}
        missing: list[str] = []
        fresh_after = None if not refresh_if_stale else now - self._refresh_ttl
        for asset_id in ordered:
            entry = self._cache.get_covering_price_series(
                self.provider_id,
                asset_id,
                frequency.value,
                price_field.value,
                start,
                end,
                not_before=fresh_after,
            )
            series = self._read_cached(entry, start, end) if entry is not None else None
            if entry is None or series is None:
                missing.append(asset_id)
            else:
                components[asset_id] = (series, entry.retrieved_at, False)
        if not missing:
            return self._compose(ordered, components, start, end, frequency, price_field)
        try:
            history = self._download(tuple(missing), start, end, frequency, price_field, now)
        except Exception as exc:
            for asset_id in missing:
                entry = self._cache.get_covering_price_series(
                    self.provider_id,
                    asset_id,
                    frequency.value,
                    price_field.value,
                    start,
                    end,
                    not_before=now - self._stale_fallback_limit,
                )
                series = self._read_cached(entry, start, end) if entry is not None else None
                if entry is None or series is None:
                    raise ExternalDataUnavailableError(
                        "Adjusted-close prices could not be retrieved."
                    ) from exc
                components[asset_id] = (series, entry.retrieved_at, True)
            return self._compose(ordered, components, start, end, frequency, price_field)
        for series in history.series:
            payload = self._serialize_series(series)
            self._cache.put_price_series(
                self.provider_id,
                series.asset_id,
                frequency.value,
                price_field.value,
                start,
                end,
                payload,
                now,
            )
            components[series.asset_id] = (series, now, False)
        self._cache.prune_price_series(
            self.provider_id, older_than=now - self._stale_fallback_limit
        )
        return self._compose(ordered, components, start, end, frequency, price_field)

    def _download(
        self,
        asset_ids: tuple[str, ...],
        start: date,
        end: date,
        frequency: ReturnFrequency,
        price_field: PriceField,
        retrieved_at: datetime,
    ) -> PriceHistory:
        if frequency is not ReturnFrequency.DAILY or price_field is not PriceField.ADJUSTED_CLOSE:
            raise ExternalDataUnavailableError("Yahoo adapter supports daily adjusted close only.")
        symbols = [yahoo_symbol(asset_id) for asset_id in asset_ids]
        frame = self._downloader(
            tickers=symbols,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=True,
            timeout=self._timeout_seconds,
            group_by="column",
        )
        if frame is None or frame.empty:
            raise ExternalDataUnavailableError("Yahoo returned no price observations.")
        series: list[AssetPriceSeries] = []
        for asset_id, symbol in zip(asset_ids, symbols, strict=True):
            values = self._adjusted_close_column(frame, symbol, len(asset_ids) == 1)
            observations: list[PriceObservation] = []
            for timestamp, value in values.items():
                numeric = float(value)
                if math.isnan(numeric) or math.isinf(numeric):
                    continue
                observed_on = pd.Timestamp(str(timestamp)).date()
                if start <= observed_on <= end:
                    observations.append(PriceObservation(observed_on, Decimal(str(numeric))))
            series.append(AssetPriceSeries(asset_id, Currency.USD, tuple(observations)))
        temporary = PriceHistory(
            asset_ids,
            tuple(series),
            start,
            end,
            frequency,
            price_field,
            DataProvenance(self.provider_id, retrieved_at, "pending"),
        )
        content_hash = temporary.calculate_content_hash()
        return PriceHistory(
            asset_ids,
            tuple(series),
            start,
            end,
            frequency,
            price_field,
            DataProvenance(self.provider_id, retrieved_at, content_hash),
        )

    @staticmethod
    def _adjusted_close_column(frame: pd.DataFrame, symbol: str, single: bool) -> pd.Series[Any]:
        if isinstance(frame.columns, pd.MultiIndex):
            try:
                return frame[("Adj Close", symbol)]
            except KeyError as exc:
                raise ExternalDataUnavailableError(
                    f"Yahoo returned no adjusted close for {symbol}."
                ) from exc
        if single and "Adj Close" in frame.columns:
            result = frame["Adj Close"]
            if isinstance(result, pd.Series):
                return result
        raise ExternalDataUnavailableError(f"Yahoo returned no adjusted close for {symbol}.")

    @staticmethod
    def _serialize_series(series: AssetPriceSeries) -> str:
        return json.dumps(
            {
                "asset_id": series.asset_id,
                "currency": series.currency.value,
                "observations": [
                    [item.observed_on.isoformat(), str(item.adjusted_close)]
                    for item in series.observations
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _read_cached(
        self, entry: PriceCacheEntry | None, start: date, end: date
    ) -> AssetPriceSeries | None:
        if entry is None:
            return None
        try:
            raw = json.loads(entry.payload)
            if raw["asset_id"] != entry.asset_id:
                raise ValueError("cached asset identity does not match its key")
            return AssetPriceSeries(
                raw["asset_id"],
                Currency(raw["currency"]),
                tuple(
                    PriceObservation(date.fromisoformat(observed_on), Decimal(price))
                    for observed_on, price in raw["observations"]
                    if start <= date.fromisoformat(observed_on) <= end
                ),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._cache.delete_price_series(entry)
            return None

    def _compose(
        self,
        ordered: tuple[str, ...],
        components: dict[str, tuple[AssetPriceSeries, datetime, bool]],
        start: date,
        end: date,
        frequency: ReturnFrequency,
        price_field: PriceField,
    ) -> PriceHistory:
        if any(asset_id not in components for asset_id in ordered):
            raise ExternalDataUnavailableError("Adjusted-close prices are incomplete.")
        series = tuple(components[asset_id][0] for asset_id in ordered)
        retrieved_at = min(components[asset_id][1] for asset_id in ordered)
        stale_fallback = any(components[asset_id][2] for asset_id in ordered)
        temporary = PriceHistory(
            ordered,
            series,
            start,
            end,
            frequency,
            price_field,
            DataProvenance(self.provider_id, retrieved_at, "pending", stale_fallback),
        )
        return PriceHistory(
            ordered,
            series,
            start,
            end,
            frequency,
            price_field,
            DataProvenance(
                self.provider_id,
                retrieved_at,
                temporary.calculate_content_hash(),
                stale_fallback,
            ),
        )
