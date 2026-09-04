from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.application import ApplicationError, PortfolioAnalysisService, subtract_calendar_years
from tests.helpers import NOW, FakeMarketDataProvider, FakeUniverseProvider, make_universe


def price_rows(start: date, count: int, initial: float, growth: float) -> list[tuple[date, str]]:
    return [(start + timedelta(days=index), str(initial * growth**index)) for index in range(count)]


def test_analysis_uses_one_aligned_fetch_and_is_reproducible() -> None:
    start = date(2025, 1, 1)
    provider = FakeMarketDataProvider(
        {
            "AAPL": price_rows(start, 253, 100, 1.001),
            "MSFT": price_rows(start, 253, 200, 1.0005),
            "SPY": price_rows(start, 253, 300, 1.0007),
        }
    )
    service = PortfolioAnalysisService(
        FakeUniverseProvider(make_universe("AAPL", "MSFT")), provider, clock=lambda: NOW
    )
    positions = [("MSFT", Decimal("1")), ("AAPL", Decimal("2"))]

    first = service.analyze(positions, start=start, end=start + timedelta(days=252))
    second = service.analyze(
        list(reversed(positions)), start=start, end=start + timedelta(days=252)
    )

    assert provider.calls == 2
    assert first.window.return_observations == 252
    assert first.valuation.valued_on == start + timedelta(days=252)
    assert first.analysis_hash == second.analysis_hash
    assert first.analytics.equal_weight_series[0].cumulative_return == 0.0
    assert sum(position.weight for position in first.valuation.positions) == Decimal(1)


def test_history_defaults_and_leap_day_are_explicit() -> None:
    assert subtract_calendar_years(date(2024, 2, 29), 3) == date(2021, 2, 28)


def test_analysis_rejects_short_or_invalid_history() -> None:
    start = date(2026, 1, 1)
    provider = FakeMarketDataProvider(
        {"AAPL": price_rows(start, 10, 100, 1.01), "SPY": price_rows(start, 10, 100, 1.01)}
    )
    service = PortfolioAnalysisService(
        FakeUniverseProvider(make_universe("AAPL")), provider, clock=lambda: NOW
    )
    with pytest.raises(ApplicationError) as short:
        service.analyze([("AAPL", Decimal("1"))], start=start, end=start + timedelta(days=20))
    assert short.value.code == "INSUFFICIENT_HISTORY"

    with pytest.raises(ApplicationError) as invalid:
        service.analyze([("AAPL", Decimal("1"))], start=date(2026, 2, 1), end=date(2026, 1, 1))
    assert invalid.value.code == "INVALID_HISTORY_WINDOW"
