"""Yahoo Finance adjusted-close adapter with persistent read-through caching."""

from __future__ import annotations

import hashlib
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
from app.infrastructure.cache import CacheEntry, SQLiteCache


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
        cache_key = self._cache_key(ordered, start, end, frequency, price_field)
        cached = self._cache.get("prices", cache_key)
        now = self._clock()
        if cached is not None and (
            not refresh_if_stale or now - cached.retrieved_at <= self._refresh_ttl
        ):
            return self._deserialize(cached, stale_fallback=False)
        try:
            history = self._download(ordered, start, end, frequency, price_field, now)
        except Exception as exc:
            if cached is not None and now - cached.retrieved_at <= self._stale_fallback_limit:
                return self._deserialize(cached, stale_fallback=True)
            raise ExternalDataUnavailableError(
                "Adjusted-close prices could not be retrieved."
            ) from exc
        payload = json.dumps(history.stable_payload(), sort_keys=True, separators=(",", ":"))
        self._cache.put("prices", cache_key, payload, now, history.provenance.content_hash)
        return history

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
    def _cache_key(
        asset_ids: tuple[str, ...],
        start: date,
        end: date,
        frequency: ReturnFrequency,
        price_field: PriceField,
    ) -> str:
        raw = json.dumps(
            [
                "yahoo_finance",
                asset_ids,
                start.isoformat(),
                end.isoformat(),
                frequency,
                price_field,
            ],
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def _deserialize(self, entry: CacheEntry, *, stale_fallback: bool) -> PriceHistory:
        raw = json.loads(entry.payload)
        series = tuple(
            AssetPriceSeries(
                item["asset_id"],
                Currency(item["currency"]),
                tuple(
                    PriceObservation(date.fromisoformat(observed_on), Decimal(price))
                    for observed_on, price in item["observations"]
                ),
            )
            for item in raw["series"]
        )
        return PriceHistory(
            tuple(raw["asset_ids"]),
            series,
            date.fromisoformat(raw["start"]),
            date.fromisoformat(raw["end"]),
            ReturnFrequency(raw["frequency"]),
            PriceField(raw["price_field"]),
            DataProvenance(
                self.provider_id, entry.retrieved_at, entry.content_hash, stale_fallback
            ),
        )
