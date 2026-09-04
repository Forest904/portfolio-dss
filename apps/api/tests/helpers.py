from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain import (
    Asset,
    AssetPriceSeries,
    Currency,
    DataProvenance,
    InvestmentUniverse,
    PriceField,
    PriceHistory,
    PriceObservation,
    ReturnFrequency,
    UniverseSnapshot,
)

NOW = datetime(2026, 9, 4, 21, 0, tzinfo=UTC)


def make_universe(*tickers: str) -> UniverseSnapshot:
    assets = tuple(
        Asset(
            id=ticker,
            ticker=ticker,
            name=f"{ticker} Incorporated",
            exchange="NASDAQ",
            currency=Currency.USD,
            sector="Technology",
            industry="Software",
            universe_memberships=frozenset({"sp500"}),
        )
        for ticker in tickers
    )
    return UniverseSnapshot(
        InvestmentUniverse(
            id="sp500",
            name="S&P 500",
            as_of_date=NOW.date(),
            asset_ids=tickers,
            benchmark_asset_id="SPY",
            benchmark_name="SPDR S&P 500 ETF Trust (total-return proxy)",
        ),
        assets,
        DataProvenance("fixture", NOW, "universe-hash"),
    )


class FakeUniverseProvider:
    def __init__(self, snapshot: UniverseSnapshot) -> None:
        self.snapshot = snapshot

    def get_current_universe(self, *, refresh_if_stale: bool = True) -> UniverseSnapshot:
        return self.snapshot


class FakeMarketDataProvider:
    def __init__(self, prices: dict[str, list[tuple[date, str]]]) -> None:
        self.prices = prices
        self.calls = 0
        self.requested_asset_ids: list[tuple[str, ...]] = []

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
        self.calls += 1
        ordered = tuple(asset_ids)
        self.requested_asset_ids.append(ordered)
        series = tuple(
            AssetPriceSeries(
                ticker,
                Currency.USD,
                tuple(
                    PriceObservation(observed_on, Decimal(value))
                    for observed_on, value in self.prices[ticker]
                ),
            )
            for ticker in ordered
        )
        provisional = PriceHistory(
            ordered,
            series,
            start,
            end,
            frequency,
            price_field,
            DataProvenance("fixture", NOW, "pending"),
        )
        return PriceHistory(
            ordered,
            series,
            start,
            end,
            frequency,
            price_field,
            DataProvenance("fixture", NOW, provisional.calculate_content_hash()),
        )
