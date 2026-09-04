from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.helpers import NOW, FakeMarketDataProvider, FakeUniverseProvider, make_universe


def client(tmp_path: Path) -> TestClient:
    universe = FakeUniverseProvider(make_universe("AAPL", "MSFT"))
    prices = FakeMarketDataProvider(
        {
            "AAPL": [(date(2026, 9, 3), "100")],
            "MSFT": [(date(2026, 9, 3), "200")],
        }
    )
    return TestClient(
        create_app(
            settings=Settings(cache_path=tmp_path / "cache.sqlite3"),
            universe_provider=universe,
            market_data_provider=prices,
            clock=lambda: NOW,
        )
    )


def test_portfolio_valuation_endpoint_returns_reproducible_snapshot(tmp_path: Path) -> None:
    api = client(tmp_path)
    payload = {
        "positions": [
            {"ticker": "msft", "quantity": "1.5"},
            {"ticker": "AAPL", "quantity": 2},
        ],
        "as_of": "2026-09-04",
    }
    first = api.post("/api/v1/portfolios/valuation", json=payload)
    second = api.post("/api/v1/portfolios/valuation", json=payload)
    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["valued_on"] == "2026-09-03"
    assert first.json()["total_market_value"] == {"amount": "500.0", "currency": "USD"}
    assert len(first.json()["snapshot_hash"]) == 64


def test_universe_and_asset_endpoints(tmp_path: Path) -> None:
    api = client(tmp_path)
    universe = api.get("/api/v1/universes/sp500")
    asset = api.get("/api/v1/assets/aapl")
    missing = api.get("/api/v1/assets/zzzz")
    assert universe.status_code == 200
    assert [item["ticker"] for item in universe.json()["assets"]] == ["AAPL", "MSFT"]
    assert asset.status_code == 200
    assert asset.json()["ticker"] == "AAPL"
    assert missing.status_code == 404
    assert missing.json()["code"] == "ASSET_NOT_FOUND"


def test_api_returns_machine_readable_validation_errors(tmp_path: Path) -> None:
    api = client(tmp_path)
    duplicate = api.post(
        "/api/v1/portfolios/valuation",
        json={
            "positions": [
                {"ticker": "aapl", "quantity": 1},
                {"ticker": " AAPL ", "quantity": 2},
            ]
        },
    )
    malformed = api.post(
        "/api/v1/portfolios/valuation",
        json={"positions": [{"ticker": "AAPL", "quantity": "not-a-number"}]},
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["code"] == "DUPLICATE_TICKER"
    assert malformed.status_code == 422
    assert malformed.json()["code"] == "REQUEST_VALIDATION_ERROR"
