"""Core portfolio entities and value objects."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from app.domain.errors import DomainValidationError

WEIGHT_SUM_TOLERANCE = 1e-8


class Currency(StrEnum):
    """Currencies supported by the Phase A/B domain."""

    USD = "USD"


class TimeHorizonUnit(StrEnum):
    """Unambiguous units for a forward-looking time horizon."""

    DAYS = "days"
    MONTHS = "months"
    YEARS = "years"


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainValidationError(f"{field_name} must be a non-empty string")


def _require_currency(value: object, field_name: str = "currency") -> None:
    if not isinstance(value, Currency):
        raise DomainValidationError(f"{field_name} must be a supported Currency")


@dataclass(frozen=True, slots=True)
class Asset:
    """An investable instrument known to the DSS."""

    id: str
    ticker: str
    name: str
    exchange: str
    currency: Currency
    sector: str
    industry: str | None = None
    universe_memberships: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        for field_name in ("id", "ticker", "name", "exchange", "sector"):
            _require_non_empty(getattr(self, field_name), field_name)
        if self.ticker != self.ticker.strip().upper():
            raise DomainValidationError("ticker must be trimmed and uppercase")
        _require_currency(self.currency)
        if self.industry is not None:
            _require_non_empty(self.industry, "industry")
        if not isinstance(self.universe_memberships, frozenset):
            raise DomainValidationError("universe_memberships must be a frozenset")
        for universe_id in self.universe_memberships:
            _require_non_empty(universe_id, "universe_membership")


@dataclass(frozen=True, slots=True)
class InvestmentUniverse:
    """A named and dated set of asset identifiers with benchmark metadata."""

    id: str
    name: str
    as_of_date: date
    asset_ids: tuple[str, ...]
    benchmark_asset_id: str
    benchmark_name: str

    def __post_init__(self) -> None:
        for field_name in ("id", "name", "benchmark_asset_id", "benchmark_name"):
            _require_non_empty(getattr(self, field_name), field_name)
        if not isinstance(self.as_of_date, date):
            raise DomainValidationError("as_of_date must be a date")
        if not isinstance(self.asset_ids, tuple) or not self.asset_ids:
            raise DomainValidationError("asset_ids must be a non-empty tuple")
        for asset_id in self.asset_ids:
            _require_non_empty(asset_id, "asset_id")
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise DomainValidationError("asset_ids must not contain duplicates")


@dataclass(frozen=True, slots=True)
class Position:
    """A non-negative quantity held in one asset."""

    asset_id: str
    quantity: Decimal

    def __post_init__(self) -> None:
        _require_non_empty(self.asset_id, "asset_id")
        if not isinstance(self.quantity, Decimal) or not self.quantity.is_finite():
            raise DomainValidationError("quantity must be a finite Decimal")
        if self.quantity < 0:
            raise DomainValidationError("quantity must be non-negative")


@dataclass(frozen=True, slots=True)
class Portfolio:
    """Positions owned by a user at a specified valuation time."""

    positions: tuple[Position, ...]
    base_currency: Currency
    valuation_time: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.positions, tuple):
            raise DomainValidationError("positions must be a tuple")
        if any(not isinstance(position, Position) for position in self.positions):
            raise DomainValidationError("positions must contain only Position values")
        asset_ids = [position.asset_id for position in self.positions]
        if len(set(asset_ids)) != len(asset_ids):
            raise DomainValidationError("positions must not contain duplicate asset IDs")
        _require_currency(self.base_currency, "base_currency")
        if not isinstance(self.valuation_time, datetime):
            raise DomainValidationError("valuation_time must be a datetime")
        if self.valuation_time.tzinfo is None or self.valuation_time.utcoffset() is None:
            raise DomainValidationError("valuation_time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class PortfolioWeights:
    """A fully invested, long-only target allocation."""

    asset_ids: tuple[str, ...]
    weights: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.asset_ids, tuple) or not self.asset_ids:
            raise DomainValidationError("asset_ids must be a non-empty tuple")
        if not isinstance(self.weights, tuple):
            raise DomainValidationError("weights must be a tuple")
        if len(self.asset_ids) != len(self.weights):
            raise DomainValidationError("asset_ids and weights must have equal lengths")
        for asset_id in self.asset_ids:
            _require_non_empty(asset_id, "asset_id")
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise DomainValidationError("asset_ids must not contain duplicates")
        for weight in self.weights:
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise DomainValidationError("weights must be numerical values")
            if not math.isfinite(weight):
                raise DomainValidationError("weights must be finite")
            if weight < 0:
                raise DomainValidationError("weights must be non-negative")
        if not math.isclose(
            math.fsum(self.weights),
            1.0,
            rel_tol=0.0,
            abs_tol=WEIGHT_SUM_TOLERANCE,
        ):
            raise DomainValidationError("weights must sum to one within tolerance")


@dataclass(frozen=True, slots=True)
class Money:
    """An exact monetary amount and its currency."""

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise DomainValidationError("amount must be a finite Decimal")
        _require_currency(self.currency)


@dataclass(frozen=True, slots=True)
class TimeHorizon:
    """A positive duration with an explicit unit."""

    value: int
    unit: TimeHorizonUnit

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int) or self.value <= 0:
            raise DomainValidationError("time horizon value must be a positive integer")
        if not isinstance(self.unit, TimeHorizonUnit):
            raise DomainValidationError("time horizon unit must be a TimeHorizonUnit")
