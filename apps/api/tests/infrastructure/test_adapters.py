from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from app.domain import ExternalDataUnavailableError, PriceField, ReturnFrequency
from app.infrastructure import SQLiteCache, WikipediaSP500Provider, YahooFinanceMarketDataProvider
from app.infrastructure.yahoo import yahoo_symbol

NOW = datetime(2026, 9, 4, 21, 0, tzinfo=UTC)


def test_yahoo_adapter_maps_symbols_and_uses_inclusive_domain_end(tmp_path: object) -> None:
    calls: list[dict[str, object]] = []
    columns = pd.MultiIndex.from_tuples([("Adj Close", "BRK-B"), ("Adj Close", "MSFT")])
    frame = pd.DataFrame(
        [[500.0, 250.0], [501.0, float("nan")]],
        index=pd.to_datetime(["2026-09-02", "2026-09-03"]),
        columns=columns,
    )

    def download(**kwargs: object) -> pd.DataFrame:
        calls.append(kwargs)
        return frame

    cache_path = tmp_path / "cache.sqlite3"  # type: ignore[operator]
    provider = YahooFinanceMarketDataProvider(
        SQLiteCache(cache_path), clock=lambda: NOW, downloader=download
    )
    history = provider.get_price_history(
        ("BRK.B", "MSFT"),
        date(2026, 9, 1),
        date(2026, 9, 3),
        ReturnFrequency.DAILY,
        PriceField.ADJUSTED_CLOSE,
    )

    assert yahoo_symbol("BRK.B") == "BRK-B"
    assert calls[0]["tickers"] == ["BRK-B", "MSFT"]
    assert calls[0]["auto_adjust"] is False
    assert calls[0]["end"] == "2026-09-04"
    assert len(history.series[1].observations) == 1
    assert history.provenance.content_hash == history.calculate_content_hash()


def test_yahoo_cache_hit_and_bounded_stale_fallback(tmp_path: object) -> None:
    frame = pd.DataFrame({"Adj Close": [100.0]}, index=pd.to_datetime(["2026-09-03"]))
    calls = 0

    def download(**_: object) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("offline")
        return frame

    cache_path = tmp_path / "cache.sqlite3"  # type: ignore[operator]
    first = YahooFinanceMarketDataProvider(
        SQLiteCache(cache_path),
        clock=lambda: NOW,
        downloader=download,
        refresh_ttl=timedelta(hours=1),
    )
    args = (
        ("AAPL",),
        date(2026, 9, 1),
        date(2026, 9, 3),
        ReturnFrequency.DAILY,
        PriceField.ADJUSTED_CLOSE,
    )
    original = first.get_price_history(*args)
    fallback = YahooFinanceMarketDataProvider(
        SQLiteCache(cache_path),
        clock=lambda: NOW + timedelta(days=2),
        downloader=download,
        refresh_ttl=timedelta(hours=1),
    ).get_price_history(*args)
    assert fallback.provenance.stale_fallback is True
    assert fallback.provenance.content_hash == original.provenance.content_hash

    too_old = YahooFinanceMarketDataProvider(
        SQLiteCache(cache_path),
        clock=lambda: NOW + timedelta(days=8),
        downloader=download,
        refresh_ttl=timedelta(hours=1),
    )
    with pytest.raises(ExternalDataUnavailableError):
        too_old.get_price_history(*args)


def test_wikipedia_loader_parses_and_reuses_snapshot(tmp_path: object) -> None:
    html = """
    <table id="constituents">
      <thead><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th>
      <th>GICS Sub-Industry</th></tr></thead>
      <tbody><tr><td><a href="https://www.nyse.com/quote/XNYS:BRK.B">BRK.B</a></td>
      <td>Berkshire Hathaway</td><td>Financials</td>
      <td>Multi-Sector Holdings</td></tr></tbody>
    </table>
    """
    cache_path = tmp_path / "cache.sqlite3"  # type: ignore[operator]
    provider = WikipediaSP500Provider(
        SQLiteCache(cache_path), clock=lambda: NOW, fetch_html=lambda: html
    )
    snapshot = provider.get_current_universe()
    assert snapshot.universe.asset_ids == ("BRK.B",)
    assert snapshot.assets[0].exchange == "NYSE"
    assert snapshot.provenance.content_hash

    cached = WikipediaSP500Provider(
        SQLiteCache(cache_path),
        clock=lambda: NOW + timedelta(hours=1),
        fetch_html=lambda: (_ for _ in ()).throw(RuntimeError("must not fetch")),
    ).get_current_universe()
    assert cached.provenance.content_hash == snapshot.provenance.content_hash


def test_sqlite_cache_does_not_leave_the_database_locked(tmp_path: object) -> None:
    cache_path = tmp_path / "disposable.sqlite3"  # type: ignore[operator]
    cache = SQLiteCache(cache_path)
    cache.put("test", "key", "{}", NOW, "hash")
    assert cache.get("test", "key") is not None
    cache_path.unlink()
    assert not cache_path.exists()
