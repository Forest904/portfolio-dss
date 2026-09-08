"""Spawn-safe, deterministic market fixtures; no network dependency."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import numpy as np

from app.application.frontier import PortfolioFrontierService
from app.application.guided import GuidedRecommendationService
from app.domain import HistoricalMeanEstimator, HistoricalSampleRiskEstimator
from app.infrastructure.bulk_history import BoundedBulkHistoryProvider
from app.infrastructure.frontier import ScipyEfficientFrontierGenerator
from app.infrastructure.guided_jobs import SQLiteGuidedRepository
from tests.helpers import NOW, FakeMarketDataProvider, FakeUniverseProvider, make_universe


def fixture_clock() -> datetime:
    return NOW


def fixture_prices(count: int = 12, observations: int = 300) -> FakeMarketDataProvider:
    rng = np.random.default_rng(6026)
    returns = rng.normal(0.0003, 0.012, (count + 1, observations - 1))
    returns += rng.normal(0, 0.005, observations - 1)
    prices = np.column_stack((np.full(count + 1, 100.0), 100 * np.cumprod(1 + returns, axis=1)))
    start = NOW.date() - timedelta(days=observations)
    assets = (*[f"S{i:03}" for i in range(count)], "SPY")
    return FakeMarketDataProvider(
        {
            asset: [
                (start + timedelta(days=j), str(Decimal(str(value)))) for j, value in enumerate(row)
            ]
            for asset, row in zip(assets, prices, strict=True)
        }
    )


@dataclass(frozen=True)
class FixtureFactory:
    count: int = 12
    observations: int = 300

    def __call__(self, repository: SQLiteGuidedRepository) -> GuidedRecommendationService:
        return fixture_service(self.count, self.observations, repository=repository)


def fixture_service(
    count: int = 12,
    observations: int = 300,
    *,
    prices: FakeMarketDataProvider | None = None,
    repository: SQLiteGuidedRepository | None = None,
) -> GuidedRecommendationService:
    provider = prices or fixture_prices(count, observations)
    universe = FakeUniverseProvider(make_universe(*[f"S{i:03}" for i in range(count)]))
    frontier = PortfolioFrontierService(
        universe,
        provider,
        HistoricalMeanEstimator(),
        HistoricalSampleRiskEstimator(),
        ScipyEfficientFrontierGenerator(),
    )
    return GuidedRecommendationService(
        universe,
        BoundedBulkHistoryProvider(provider),
        frontier,
        cache=repository,
        clock=fixture_clock,
    )
