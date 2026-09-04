"""Current S&P 500 constituent adapter backed by Wikipedia."""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from app.domain import (
    SP500_BENCHMARK_ASSET_ID,
    SP500_BENCHMARK_NAME,
    SP500_UNIVERSE_ID,
    Asset,
    Currency,
    DataProvenance,
    ExternalDataUnavailableError,
    InvestmentUniverse,
    UniverseSnapshot,
)
from app.infrastructure.cache import CacheEntry, SQLiteCache

WIKIPEDIA_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


class WikipediaSP500Provider:
    provider_id = "wikipedia"

    def __init__(
        self,
        cache: SQLiteCache,
        *,
        timeout_seconds: float = 15.0,
        refresh_ttl: timedelta = timedelta(hours=24),
        stale_fallback_limit: timedelta = timedelta(days=7),
        clock: Callable[[], datetime] | None = None,
        fetch_html: Callable[[], str] | None = None,
    ) -> None:
        self._cache = cache
        self._timeout_seconds = timeout_seconds
        self._refresh_ttl = refresh_ttl
        self._stale_fallback_limit = stale_fallback_limit
        self._clock = clock or (lambda: datetime.now(UTC))
        self._fetch_html = fetch_html or self._download_html
        self._loaded: UniverseSnapshot | None = None

    def _download_html(self) -> str:
        response = httpx.get(
            WIKIPEDIA_SP500_URL,
            timeout=self._timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "PortfolioDSS/0.2 (https://github.com/Forest904/portfolio-dss; educational)"
                )
            },
        )
        response.raise_for_status()
        return response.text

    def get_current_universe(self, *, refresh_if_stale: bool = True) -> UniverseSnapshot:
        now = self._clock()
        if self._loaded is not None and (
            not refresh_if_stale or now - self._loaded.provenance.retrieved_at <= self._refresh_ttl
        ):
            return self._loaded
        cached = self._cache.get("universe", SP500_UNIVERSE_ID)
        if cached is not None and (
            not refresh_if_stale or now - cached.retrieved_at <= self._refresh_ttl
        ):
            self._loaded = self._deserialize(cached, stale_fallback=False)
            return self._loaded
        try:
            snapshot = self._parse(self._fetch_html(), now)
        except Exception as exc:
            if cached is not None and now - cached.retrieved_at <= self._stale_fallback_limit:
                self._loaded = self._deserialize(cached, stale_fallback=True)
                return self._loaded
            raise ExternalDataUnavailableError(
                "Current S&P 500 constituents could not be retrieved."
            ) from exc
        payload = self._serialize(snapshot)
        self._cache.put(
            "universe", SP500_UNIVERSE_ID, payload, now, snapshot.provenance.content_hash
        )
        self._loaded = snapshot
        return snapshot

    def list_assets(self) -> tuple[Asset, ...]:
        return self.get_current_universe().assets

    def get_asset(self, ticker: str) -> Asset | None:
        normalized = ticker.strip().upper()
        return next(
            (asset for asset in self.get_current_universe().assets if asset.ticker == normalized),
            None,
        )

    def _parse(self, html: str, retrieved_at: datetime) -> UniverseSnapshot:
        try:
            tables = pd.read_html(io.StringIO(html), match="Symbol")
            table = next(
                item
                for item in tables
                if {"Symbol", "Security", "GICS Sector", "GICS Sub-Industry"}.issubset(item.columns)
            )
        except Exception as exc:
            raise ExternalDataUnavailableError("Wikipedia constituent table is malformed.") from exc
        exchanges = self._extract_exchanges(html)
        assets = tuple(
            sorted(
                (
                    Asset(
                        id=str(row["Symbol"]).strip().upper(),
                        ticker=str(row["Symbol"]).strip().upper(),
                        name=str(row["Security"]).strip(),
                        exchange=exchanges.get(str(row["Symbol"]).strip().upper(), "UNKNOWN"),
                        currency=Currency.USD,
                        sector=str(row["GICS Sector"]).strip(),
                        industry=str(row["GICS Sub-Industry"]).strip(),
                        universe_memberships=frozenset({SP500_UNIVERSE_ID}),
                    )
                    for _, row in table.iterrows()
                ),
                key=lambda asset: asset.ticker,
            )
        )
        if not assets:
            raise ExternalDataUnavailableError("Wikipedia returned an empty constituent table.")
        payload = self._assets_payload(assets, retrieved_at.date().isoformat())
        content_hash = hashlib.sha256(payload.encode()).hexdigest()
        universe = InvestmentUniverse(
            id=SP500_UNIVERSE_ID,
            name="S&P 500",
            as_of_date=retrieved_at.date(),
            asset_ids=tuple(asset.id for asset in assets),
            benchmark_asset_id=SP500_BENCHMARK_ASSET_ID,
            benchmark_name=SP500_BENCHMARK_NAME,
        )
        return UniverseSnapshot(
            universe,
            assets,
            DataProvenance(self.provider_id, retrieved_at, content_hash),
        )

    @staticmethod
    def _extract_exchanges(html: str) -> dict[str, str]:
        exchanges: dict[str, str] = {}
        table = BeautifulSoup(html, "html.parser").find("table", id="constituents")
        if table is None:
            return exchanges
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            ticker = cells[0].get_text(strip=True).upper()
            link = cells[0].find("a", href=True)
            href = str(link["href"]).lower() if link is not None else ""
            if "nasdaq.com" in href or "xnas:" in href:
                exchanges[ticker] = "NASDAQ"
            elif "nyse.com" in href or "xnys:" in href:
                exchanges[ticker] = "NYSE"
        return exchanges

    @staticmethod
    def _assets_payload(assets: tuple[Asset, ...], as_of: str) -> str:
        return json.dumps(
            {
                "as_of": as_of,
                "assets": [
                    {
                        "ticker": asset.ticker,
                        "name": asset.name,
                        "exchange": asset.exchange,
                        "sector": asset.sector,
                        "industry": asset.industry,
                    }
                    for asset in assets
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _serialize(self, snapshot: UniverseSnapshot) -> str:
        return self._assets_payload(snapshot.assets, snapshot.universe.as_of_date.isoformat())

    def _deserialize(self, entry: CacheEntry, *, stale_fallback: bool) -> UniverseSnapshot:
        raw = json.loads(entry.payload)
        assets = tuple(
            Asset(
                id=item["ticker"],
                ticker=item["ticker"],
                name=item["name"],
                exchange=item["exchange"],
                currency=Currency.USD,
                sector=item["sector"],
                industry=item["industry"],
                universe_memberships=frozenset({SP500_UNIVERSE_ID}),
            )
            for item in raw["assets"]
        )
        universe = InvestmentUniverse(
            id=SP500_UNIVERSE_ID,
            name="S&P 500",
            as_of_date=datetime.fromisoformat(raw["as_of"]).date(),
            asset_ids=tuple(asset.id for asset in assets),
            benchmark_asset_id=SP500_BENCHMARK_ASSET_ID,
            benchmark_name=SP500_BENCHMARK_NAME,
        )
        return UniverseSnapshot(
            universe,
            assets,
            DataProvenance(
                self.provider_id, entry.retrieved_at, entry.content_hash, stale_fallback
            ),
        )
