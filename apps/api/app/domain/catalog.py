"""Asset-catalog and current-universe contracts."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.market_data import DataProvenance
from app.domain.models import Asset, InvestmentUniverse


@dataclass(frozen=True, slots=True)
class UniverseSnapshot:
    universe: InvestmentUniverse
    assets: tuple[Asset, ...]
    provenance: DataProvenance


class AssetCatalog(Protocol):
    def get_asset(self, ticker: str) -> Asset | None: ...

    def list_assets(self) -> tuple[Asset, ...]: ...


class CurrentUniverseProvider(Protocol):
    def get_current_universe(self, *, refresh_if_stale: bool = True) -> UniverseSnapshot: ...
