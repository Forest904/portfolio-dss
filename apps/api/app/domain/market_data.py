"""Framework-independent market-data contracts and values."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.conventions import PriceField, ReturnFrequency
from app.domain.errors import DomainValidationError
from app.domain.models import Currency


@dataclass(frozen=True, slots=True)
class DataProvenance:
    provider: str
    retrieved_at: datetime
    content_hash: str
    stale_fallback: bool = False

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise DomainValidationError("provider must be non-empty")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise DomainValidationError("retrieved_at must be timezone-aware")
        if not self.content_hash.strip():
            raise DomainValidationError("content_hash must be non-empty")


@dataclass(frozen=True, slots=True)
class PriceObservation:
    observed_on: date
    adjusted_close: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.observed_on, date):
            raise DomainValidationError("observed_on must be a date")
        if not isinstance(self.adjusted_close, Decimal) or not self.adjusted_close.is_finite():
            raise DomainValidationError("adjusted_close must be a finite Decimal")
        if self.adjusted_close <= 0:
            raise DomainValidationError("adjusted_close must be positive")


@dataclass(frozen=True, slots=True)
class AssetPriceSeries:
    asset_id: str
    currency: Currency
    observations: tuple[PriceObservation, ...]

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise DomainValidationError("asset_id must be non-empty")
        if not isinstance(self.currency, Currency):
            raise DomainValidationError("currency must be supported")
        dates = [item.observed_on for item in self.observations]
        if dates != sorted(dates):
            raise DomainValidationError("price timestamps must be monotonic")
        if len(dates) != len(set(dates)):
            raise DomainValidationError("price timestamps must not contain duplicates")


@dataclass(frozen=True, slots=True)
class PriceHistory:
    asset_ids: tuple[str, ...]
    series: tuple[AssetPriceSeries, ...]
    start: date
    end: date
    frequency: ReturnFrequency
    price_field: PriceField
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if not self.asset_ids or len(set(self.asset_ids)) != len(self.asset_ids):
            raise DomainValidationError("asset_ids must be non-empty and unique")
        if self.start > self.end:
            raise DomainValidationError("price-history start must not follow end")

    def stable_payload(self) -> dict[str, object]:
        return {
            "asset_ids": list(self.asset_ids),
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "frequency": self.frequency.value,
            "price_field": self.price_field.value,
            "series": [
                {
                    "asset_id": item.asset_id,
                    "currency": item.currency.value,
                    "observations": [
                        [observation.observed_on.isoformat(), str(observation.adjusted_close)]
                        for observation in item.observations
                    ],
                }
                for item in self.series
            ],
        }

    def calculate_content_hash(self) -> str:
        payload = json.dumps(self.stable_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class MarketDataProvider(Protocol):
    """Port used by application services to retrieve normalized price data."""

    def get_price_history(
        self,
        asset_ids: Sequence[str],
        start: date,
        end: date,
        frequency: ReturnFrequency,
        price_field: PriceField,
        *,
        refresh_if_stale: bool = True,
    ) -> PriceHistory: ...
