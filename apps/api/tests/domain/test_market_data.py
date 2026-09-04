from datetime import date
from decimal import Decimal

import pytest

from app.domain import AssetPriceSeries, Currency, DomainValidationError, PriceObservation


def test_price_observation_requires_positive_finite_decimal() -> None:
    with pytest.raises(DomainValidationError):
        PriceObservation(date(2026, 1, 1), Decimal("0"))
    with pytest.raises(DomainValidationError):
        PriceObservation(date(2026, 1, 1), Decimal("NaN"))


def test_price_series_rejects_duplicate_or_non_monotonic_dates() -> None:
    first = PriceObservation(date(2026, 1, 2), Decimal("10"))
    second = PriceObservation(date(2026, 1, 1), Decimal("11"))
    with pytest.raises(DomainValidationError, match="monotonic"):
        AssetPriceSeries("AAPL", Currency.USD, (first, second))
    with pytest.raises(DomainValidationError, match="duplicates"):
        AssetPriceSeries("AAPL", Currency.USD, (first, first))
