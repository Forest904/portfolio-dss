from datetime import date
from decimal import Decimal

import pytest

from app.application import ApplicationError, PortfolioValuationService
from tests.helpers import NOW, FakeMarketDataProvider, FakeUniverseProvider, make_universe


def service(prices: dict[str, list[tuple[date, str]]]) -> PortfolioValuationService:
    return PortfolioValuationService(
        FakeUniverseProvider(make_universe(*prices)),
        FakeMarketDataProvider(prices),
        clock=lambda: NOW,
    )


def test_values_on_latest_common_date_and_is_permutation_invariant() -> None:
    prices = {
        "AAPL": [(date(2026, 9, 2), "100"), (date(2026, 9, 3), "110")],
        "MSFT": [(date(2026, 9, 2), "200")],
    }
    valuator = service(prices)
    first = valuator.value([(" msft ", Decimal("1.5")), ("aapl", Decimal("2"))], date(2026, 9, 4))
    second = valuator.value([("AAPL", Decimal("2")), ("MSFT", Decimal("1.5"))], date(2026, 9, 4))
    assert first.valued_on == date(2026, 9, 2)
    assert first.total_market_value == Decimal("500.0")
    assert [item.ticker for item in first.positions] == ["AAPL", "MSFT"]
    assert first.snapshot_hash == second.snapshot_hash
    assert sum((item.weight for item in first.positions), Decimal(0)) == Decimal(1)


@pytest.mark.parametrize(
    "positions,code",
    [
        ([], "EMPTY_PORTFOLIO"),
        ([("AAPL", Decimal("0"))], "INVALID_QUANTITY"),
        ([("aapl", Decimal("1")), (" AAPL ", Decimal("2"))], "DUPLICATE_TICKER"),
        ([("ZZZZ", Decimal("1"))], "UNSUPPORTED_TICKER"),
    ],
)
def test_rejects_invalid_portfolios(positions: list[tuple[str, Decimal]], code: str) -> None:
    valuator = PortfolioValuationService(
        FakeUniverseProvider(make_universe("AAPL")),
        FakeMarketDataProvider({"AAPL": [(date(2026, 9, 3), "100")]}),
        clock=lambda: NOW,
    )
    with pytest.raises(ApplicationError) as caught:
        valuator.value(positions, date(2026, 9, 4))
    assert caught.value.code == code


def test_rejects_stale_and_unaligned_data() -> None:
    with pytest.raises(ApplicationError) as stale:
        service({"AAPL": [(date(2026, 8, 20), "100")]}).value(
            [("AAPL", Decimal("1"))], date(2026, 9, 4)
        )
    assert stale.value.code == "STALE_VALUATION_DATA"

    with pytest.raises(ApplicationError) as unaligned:
        service(
            {
                "AAPL": [(date(2026, 9, 2), "100")],
                "MSFT": [(date(2026, 9, 3), "200")],
            }
        ).value([("AAPL", Decimal("1")), ("MSFT", Decimal("1"))], date(2026, 9, 4))
    assert unaligned.value.code == "INSUFFICIENT_ALIGNED_DATA"


def test_rejects_future_date() -> None:
    with pytest.raises(ApplicationError) as caught:
        service({"AAPL": [(date(2026, 9, 3), "100")]}).value(
            [("AAPL", Decimal("1"))], date(2026, 9, 5)
        )
    assert caught.value.code == "INVALID_AS_OF"
