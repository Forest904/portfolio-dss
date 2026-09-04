from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.helpers import NOW, FakeMarketDataProvider, FakeUniverseProvider, make_universe


def rows(start: date, initial: float, daily_growth: float) -> list[tuple[date, str]]:
    return [
        (start + timedelta(days=index), str(initial * daily_growth**index)) for index in range(253)
    ]


def test_analysis_endpoint_returns_typed_historical_report(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    market_data = FakeMarketDataProvider(
        {
            "AAPL": rows(start, 100, 1.0),
            "MSFT": rows(start, 200, 1.001),
            "SPY": rows(start, 300, 1.0005),
        }
    )
    api = TestClient(
        create_app(
            settings=Settings(cache_path=tmp_path / "cache.sqlite3"),
            universe_provider=FakeUniverseProvider(make_universe("AAPL", "MSFT")),
            market_data_provider=market_data,
            clock=lambda: NOW,
        )
    )
    response = api.post(
        "/api/v1/portfolios/analyze",
        json={
            "positions": [
                {"ticker": "msft", "quantity": "1"},
                {"ticker": "AAPL", "quantity": "2"},
            ],
            "history": {
                "start": start.isoformat(),
                "end": (start + timedelta(days=252)).isoformat(),
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["window"]["return_observations"] == 252
    assert len(payload["series"]) == 253
    assert payload["series"][0]["current"]["daily_return"] is None
    assert payload["series"][0]["current"]["cumulative_return"] == 0.0
    assert payload["covariance"]["asset_ids"] == ["AAPL", "MSFT"]
    assert payload["correlation"]["values"][0] == [None, None]
    assert "AAPL" in payload["diagnostics"][0]
    assert payload["concentration"]["assets"]["largest_id"] == "MSFT"
    assert len(payload["analysis_hash"]) == 64
    assert market_data.calls == 1


def test_analysis_endpoint_returns_machine_readable_window_error(tmp_path: Path) -> None:
    start = date(2026, 1, 1)
    api = TestClient(
        create_app(
            settings=Settings(cache_path=tmp_path / "cache.sqlite3"),
            universe_provider=FakeUniverseProvider(make_universe("AAPL")),
            market_data_provider=FakeMarketDataProvider(
                {"AAPL": rows(start, 100, 1.0), "SPY": rows(start, 100, 1.0)}
            ),
            clock=lambda: NOW,
        )
    )
    response = api.post(
        "/api/v1/portfolios/analyze",
        json={
            "positions": [{"ticker": "AAPL", "quantity": 1}],
            "history": {"start": "2026-02-01", "end": "2026-01-01"},
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_HISTORY_WINDOW"
