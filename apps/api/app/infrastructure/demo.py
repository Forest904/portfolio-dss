"""Deterministic offline adapters used only by the supported course demo."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np

from app.application.frontier import PortfolioFrontierService
from app.application.guided import GuidedRecommendationService
from app.domain import (
    Asset,
    AssetPriceSeries,
    Currency,
    DataProvenance,
    HistoricalMeanEstimator,
    HistoricalSampleRiskEstimator,
    InvestmentUniverse,
    PriceField,
    PriceHistory,
    PriceObservation,
    ReturnFrequency,
    UniverseSnapshot,
)
from app.infrastructure.bulk_history import BoundedBulkHistoryProvider
from app.infrastructure.frontier import ScipyEfficientFrontierGenerator
from app.infrastructure.guided_jobs import SQLiteGuidedRepository

DEMO_NOW = datetime(2025, 12, 31, 17, 0, tzinfo=UTC)
DEMO_TICKERS = ("AAPL", "MSFT", *tuple(f"S{i:03}" for i in range(28)))


class DemoDataProvider:
    def __init__(self, observations: int = 756) -> None:
        rng = np.random.default_rng(6026)
        returns = rng.normal(0.0003, 0.012, (len(DEMO_TICKERS) + 1, observations - 1))
        returns += rng.normal(0, 0.005, observations - 1)
        values = np.column_stack(
            (
                np.full(len(DEMO_TICKERS) + 1, 100.0),
                100 * np.cumprod(1 + returns, axis=1),
            )
        )
        first = DEMO_NOW.date() - timedelta(days=observations - 1)
        self.prices = {
            asset: tuple(
                PriceObservation(first + timedelta(days=index), Decimal(str(value)))
                for index, value in enumerate(row)
            )
            for asset, row in zip((*DEMO_TICKERS, "SPY"), values, strict=True)
        }

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
        series = tuple(
            AssetPriceSeries(
                asset,
                Currency.USD,
                tuple(item for item in self.prices[asset] if start <= item.observed_on <= end),
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
            DataProvenance("synthetic_demo", DEMO_NOW, "pending"),
        )
        return PriceHistory(
            ordered,
            series,
            start,
            end,
            frequency,
            price_field,
            DataProvenance("synthetic_demo", DEMO_NOW, provisional.calculate_content_hash()),
        )


class DemoUniverseProvider:
    def __init__(self) -> None:
        assets = tuple(
            Asset(
                ticker,
                ticker,
                f"Synthetic demo company {ticker}",
                "DEMO",
                Currency.USD,
                ("Technology", "Health Care", "Financials", "Energy")[index % 4],
                "Synthetic fixture",
                frozenset({"sp500-demo"}),
            )
            for index, ticker in enumerate(DEMO_TICKERS)
        )
        self.snapshot = UniverseSnapshot(
            InvestmentUniverse(
                "sp500-demo",
                "Synthetic S&P 500 workflow demonstration",
                DEMO_NOW.date(),
                DEMO_TICKERS,
                "SPY",
                "Synthetic SPY total-return proxy",
            ),
            assets,
            DataProvenance("synthetic_demo", DEMO_NOW, "demo-universe-v1"),
        )

    def get_current_universe(self, *, refresh_if_stale: bool = True) -> UniverseSnapshot:
        return self.snapshot


@dataclass(frozen=True)
class DemoGuidedFactory:
    def __call__(self, repository: SQLiteGuidedRepository) -> GuidedRecommendationService:
        universe = DemoUniverseProvider()
        prices = DemoDataProvider()
        frontier = PortfolioFrontierService(
            universe,
            prices,
            HistoricalMeanEstimator(),
            HistoricalSampleRiskEstimator(),
            ScipyEfficientFrontierGenerator(),
            clock=lambda: DEMO_NOW,
        )
        return GuidedRecommendationService(
            universe,
            BoundedBulkHistoryProvider(prices),
            frontier,
            cache=repository,
            clock=lambda: DEMO_NOW,
            configuration_key="synthetic-demo-v1",
        )
