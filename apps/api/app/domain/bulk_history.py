"""Partial market-data retrieval contract; failures are explicit."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.domain.market_data import AssetPriceSeries, DataProvenance


@dataclass(frozen=True, slots=True)
class HistoryFailure:
    asset_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class BulkHistory:
    series: tuple[AssetPriceSeries, ...]
    failures: tuple[HistoryFailure, ...]
    provenance: tuple[DataProvenance, ...]


class BulkHistoryProvider(Protocol):
    def get_bulk_history(
        self,
        asset_ids: tuple[str, ...],
        start: date,
        end: date,
    ) -> BulkHistory: ...
