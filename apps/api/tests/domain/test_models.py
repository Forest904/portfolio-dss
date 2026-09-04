from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.domain import (
    Asset,
    Currency,
    DomainValidationError,
    InvestmentUniverse,
    Money,
    Portfolio,
    PortfolioWeights,
    Position,
    TimeHorizon,
    TimeHorizonUnit,
)


def make_position(asset_id: str = "AAPL") -> Position:
    return Position(asset_id=asset_id, quantity=Decimal("1.5"))


def test_asset_is_immutable_and_requires_supported_currency() -> None:
    asset = Asset(
        id="AAPL",
        ticker="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        currency=Currency.USD,
        sector="Information Technology",
        universe_memberships=frozenset({"sp500"}),
    )
    assert asset.ticker == "AAPL"

    with pytest.raises(DomainValidationError):
        Asset(
            id="AIR",
            ticker="AIR",
            name="Example",
            exchange="NYSE",
            currency="EUR",  # type: ignore[arg-type]
            sector="Industrials",
        )


def test_asset_rejects_noncanonical_ticker() -> None:
    with pytest.raises(DomainValidationError):
        Asset(
            id="AAPL",
            ticker="aapl",
            name="Apple Inc.",
            exchange="NASDAQ",
            currency=Currency.USD,
            sector="Information Technology",
        )


def test_universe_rejects_duplicate_assets() -> None:
    with pytest.raises(DomainValidationError):
        InvestmentUniverse(
            id="sp500",
            name="S&P 500",
            as_of_date=date(2026, 9, 4),
            asset_ids=("AAPL", "AAPL"),
            benchmark_asset_id="SPY",
            benchmark_name="S&P 500 proxy",
        )


@pytest.mark.parametrize("quantity", [Decimal("-0.01"), Decimal("NaN")])
def test_position_rejects_invalid_quantity(quantity: Decimal) -> None:
    with pytest.raises(DomainValidationError):
        Position(asset_id="AAPL", quantity=quantity)


def test_portfolio_rejects_duplicate_assets() -> None:
    with pytest.raises(DomainValidationError):
        Portfolio(
            positions=(make_position(), make_position()),
            base_currency=Currency.USD,
            valuation_time=datetime.now(UTC),
        )


def test_portfolio_requires_timezone_aware_valuation_time() -> None:
    with pytest.raises(DomainValidationError):
        Portfolio(
            positions=(make_position(),),
            base_currency=Currency.USD,
            valuation_time=datetime(2026, 9, 4),
        )


def test_portfolio_weights_accept_sum_inside_tolerance() -> None:
    weights = PortfolioWeights(
        asset_ids=("AAPL", "MSFT"),
        weights=(0.5, 0.500000005),
    )
    assert weights.asset_ids == ("AAPL", "MSFT")


@pytest.mark.parametrize(
    "asset_ids,weights",
    [
        (("AAPL", "AAPL"), (0.5, 0.5)),
        (("AAPL", "MSFT"), (1.0,)),
        (("AAPL", "MSFT"), (1.1, -0.1)),
        (("AAPL", "MSFT"), (0.4, 0.5)),
        (("AAPL", "MSFT"), (float("nan"), 1.0)),
        (("AAPL", "MSFT"), (float("inf"), 0.0)),
    ],
)
def test_portfolio_weights_reject_invalid_allocations(
    asset_ids: tuple[str, ...], weights: tuple[float, ...]
) -> None:
    with pytest.raises(DomainValidationError):
        PortfolioWeights(asset_ids=asset_ids, weights=weights)


def test_money_requires_decimal_and_supported_currency() -> None:
    assert Money(Decimal("100.00"), Currency.USD).amount == Decimal("100.00")
    with pytest.raises(DomainValidationError):
        Money(100.0, Currency.USD)  # type: ignore[arg-type]
    with pytest.raises(DomainValidationError):
        Money(Decimal("100.00"), "EUR")  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1, True, 2.5])
def test_time_horizon_requires_positive_integer(value: object) -> None:
    with pytest.raises(DomainValidationError):
        TimeHorizon(value=value, unit=TimeHorizonUnit.YEARS)  # type: ignore[arg-type]


def test_time_horizon_requires_known_unit() -> None:
    with pytest.raises(DomainValidationError):
        TimeHorizon(value=2, unit="years")  # type: ignore[arg-type]
