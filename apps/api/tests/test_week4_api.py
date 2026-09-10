from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain import OptimizationRequest, OptimizationSolverError
from app.main import create_app
from tests.helpers import NOW, FakeMarketDataProvider, FakeUniverseProvider, make_universe


def varying_rows(start: date, initial: float, returns: tuple[float, ...]) -> list[tuple[date, str]]:
    price = initial
    rows = [(start, str(price))]
    for index in range(252):
        price *= 1.0 + returns[index % len(returns)]
        rows.append((start + timedelta(days=index + 1), str(price)))
    return rows


def client(tmp_path: Path, provider: FakeMarketDataProvider, **kwargs: object) -> TestClient:
    return TestClient(
        create_app(
            settings=Settings(cache_path=tmp_path / "cache.sqlite3"),
            universe_provider=FakeUniverseProvider(make_universe("AAPL", "MSFT")),
            market_data_provider=provider,
            clock=lambda: NOW,
            **kwargs,  # type: ignore[arg-type]
        )
    )


def test_optimize_endpoint_returns_valid_recommended_allocation(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    provider = FakeMarketDataProvider(
        {
            "SPY": varying_rows(start, 300.0, (0.005, -0.003, 0.002)),
            "AAPL": varying_rows(start, 100.0, (0.012, -0.006, 0.004)),
            "MSFT": varying_rows(start, 200.0, (0.004, -0.002, 0.003)),
        }
    )
    api = client(tmp_path, provider)
    request = {
        "positions": [
            {"ticker": "MSFT", "quantity": "1"},
            {"ticker": "AAPL", "quantity": "2"},
        ],
        "risk_aversion": 2.0,
        "constraints": {"max_weight": 0.6},
        "history": {
            "start": start.isoformat(),
            "end": (start + timedelta(days=252)).isoformat(),
        },
    }

    first = api.post("/api/v1/portfolios/optimize", json=request)
    second = api.post("/api/v1/portfolios/optimize", json=request)

    assert first.status_code == 200
    payload = first.json()
    recommended = [item["recommended_weight"] for item in payload["allocations"]]
    assert sum(recommended) == pytest.approx(1.0, abs=1e-8)
    assert min(recommended) >= 0.0
    assert max(recommended) <= 0.6 + 1e-8
    assert payload["expected_return_model"]["asset_ids"] == ["AAPL", "MSFT"]
    assert payload["risk_model"]["observations"] == 252
    assert payload["solver"]["success"] is True
    assert payload["comparison"]["objective_change"] == pytest.approx(
        payload["comparison"]["recommended"]["objective_value"]
        - payload["comparison"]["current"]["objective_value"]
    )
    assert payload["optimization_hash"] == second.json()["optimization_hash"]
    assert provider.calls == 2
    assert provider.requested_asset_ids == [("AAPL", "MSFT", "SPY"), ("AAPL", "MSFT", "SPY")]


def test_optimize_endpoint_rejects_infeasible_cap_without_fetching_data(tmp_path: Path) -> None:
    provider = FakeMarketDataProvider({})
    response = client(tmp_path, provider).post(
        "/api/v1/portfolios/optimize",
        json={
            "positions": [
                {"ticker": "AAPL", "quantity": 1},
                {"ticker": "MSFT", "quantity": 1},
            ],
            "risk_aversion": 1,
            "constraints": {"max_weight": 0.4},
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INFEASIBLE_CONSTRAINTS"
    assert provider.calls == 0


class FailingOptimizer:
    def optimize(self, request: OptimizationRequest) -> object:
        raise OptimizationSolverError(
            "raw internal failure",
            details={"solver": "fixture", "status_code": 9},
        )


def test_optimize_endpoint_sanitizes_solver_failure(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    provider = FakeMarketDataProvider(
        {
            "SPY": varying_rows(start, 300.0, (0.005, -0.003, 0.002)),
            "AAPL": varying_rows(start, 100.0, (0.01, -0.005)),
            "MSFT": varying_rows(start, 100.0, (0.005, -0.002)),
        }
    )
    response = client(tmp_path, provider, portfolio_optimizer=FailingOptimizer()).post(
        "/api/v1/portfolios/optimize",
        json={
            "positions": [
                {"ticker": "AAPL", "quantity": 1},
                {"ticker": "MSFT", "quantity": 1},
            ],
            "risk_aversion": 1,
            "history": {
                "start": start.isoformat(),
                "end": (start + timedelta(days=252)).isoformat(),
            },
        },
    )

    assert response.status_code == 500
    assert response.json() == {
        "code": "OPTIMIZATION_FAILED",
        "message": "The optimizer could not produce a valid recommended allocation.",
        "details": {"solver": "fixture", "status_code": 9},
    }
