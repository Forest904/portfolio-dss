from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, load_settings
from app.domain import ExternalDataUnavailableError, OptimizationSolverError
from app.domain.frontier import FrontierRequest, FrontierResult, ProfileConfiguration
from app.main import create_app
from tests.helpers import NOW, FakeMarketDataProvider, FakeUniverseProvider, make_universe
from tests.test_week4_api import varying_rows

START = date(2025, 1, 1)
REQUEST = {
    "positions": [{"ticker": "AAPL", "quantity": "10"}, {"ticker": "MSFT", "quantity": "4"}],
    "history": {"start": START.isoformat(), "end": (START + timedelta(days=252)).isoformat()},
}


def provider() -> FakeMarketDataProvider:
    return FakeMarketDataProvider(
        {
            "AAPL": varying_rows(START, 100, (0.012, -0.006, 0.004)),
            "MSFT": varying_rows(START, 200, (0.004, -0.002, 0.003)),
            "SPY": varying_rows(START, 300, (0.005, -0.003, 0.002)),
        }
    )


def client(tmp_path: Path, prices: FakeMarketDataProvider, **kwargs: object) -> TestClient:
    return TestClient(
        create_app(
            settings=Settings(cache_path=tmp_path / "cache.sqlite3"),
            universe_provider=FakeUniverseProvider(make_universe("AAPL", "MSFT")),
            market_data_provider=prices,
            clock=lambda: NOW,
            **kwargs,  # type: ignore[arg-type]
        )
    )


def test_frontier_report_matches_shared_inputs_and_deterministic_facts(tmp_path: Path) -> None:
    prices = provider()
    api = client(tmp_path, prices)
    response = api.post("/api/v1/portfolios/frontier", json=REQUEST)
    assert response.status_code == 200, response.text
    report = response.json()
    repeated = api.post("/api/v1/portfolios/frontier", json=REQUEST).json()
    assert report["report_hash"] == repeated["report_hash"]
    assert prices.requested_asset_ids == [("AAPL", "MSFT", "SPY")] * 2
    assert report["expected_return_model"]["asset_ids"] == ["AAPL", "MSFT"]
    assert report["benchmark_expected_return_model"]["asset_ids"] == ["SPY"]
    assert len(report["frontier"]["points"]) == 21
    for key in ("risk_model", "benchmark_risk_model", "benchmark_expected_return_model"):
        for field in (
            "estimation_start",
            "estimation_end",
            "observations",
            "annualization_periods",
        ):
            assert report[key][field] == report["expected_return_model"][field]
    for profile in report["frontier"]["profiles"]:
        point = next(p for p in report["frontier"]["points"] if p["id"] == profile["point_id"])
        assert "objective_value" not in point["metrics"]
        for reference in report["references"]:
            fact = next(
                f
                for f in report["facts"]
                if f["id"] == f"{profile['name']}.{reference['id']}.expected_return_change"
            )
            assert fact["value"] == pytest.approx(
                100
                * (point["metrics"]["expected_return"] - reference["metrics"]["expected_return"])
            )
            assert fact["unit"] == "percentage_points"
        allocation_facts = [
            f
            for f in report["facts"]
            if f["profile"] == profile["name"] and f["kind"] == "allocation_change"
        ]
        assert sum(f["value"] for f in allocation_facts) == pytest.approx(0, abs=1e-8)
        concentration = next(
            f for f in report["facts"] if f["id"] == f"{profile['name']}.concentration"
        )
        assert concentration["value"] == pytest.approx(
            sum(w * w for w in point["weights"]["weights"])
        )


def test_cap_status_and_collapsed_alternatives(tmp_path: Path) -> None:
    response = client(tmp_path, provider()).post(
        "/api/v1/portfolios/frontier", json={**REQUEST, "constraints": {"max_weight": 0.5}}
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert len(report["frontier"]["points"]) == 1
    assert len(report["frontier"]["profiles"]) == 3
    assert [r["constraint_status"] for r in report["references"]] == [
        "exceeds_max_weight",
        "valid",
        "outside_investable_universe",
    ]
    assert len([f for f in report["facts"] if f["kind"] == "binding_cap"]) == 6


def test_configured_fractions_and_hash_ignore_retrieval_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prices = provider()
    universe = FakeUniverseProvider(make_universe("AAPL", "MSFT"))
    config = Settings(
        tmp_path / "cache.sqlite3", frontier_profiles=ProfileConfiguration((0.23, 0.51, 0.87))
    )
    api = TestClient(
        create_app(
            settings=config,
            universe_provider=universe,
            market_data_provider=prices,
            clock=lambda: NOW,
        )
    )
    first = api.post("/api/v1/portfolios/frontier", json=REQUEST).json()
    universe.snapshot = replace(
        universe.snapshot,
        provenance=replace(universe.snapshot.provenance, retrieved_at=NOW + timedelta(hours=1)),
    )
    monkeypatch.setattr("tests.helpers.NOW", NOW + timedelta(hours=1))
    second = api.post("/api/v1/portfolios/frontier", json=REQUEST).json()
    assert first["report_hash"] == second["report_hash"]
    assert first["profile_configuration"]["fractions"] == [0.23, 0.51, 0.87]
    assert len(first["frontier"]["points"]) == 24
    default = client(tmp_path, provider()).post("/api/v1/portfolios/frontier", json=REQUEST).json()
    assert first["report_hash"] != default["report_hash"]


def test_validation_happens_before_fetch(tmp_path: Path) -> None:
    prices = provider()
    api = client(tmp_path, prices)
    for changes in (
        {"constraints": {"max_weight": 0.4}},
        {"constraints": {"max_weight": 0}},
        {"risk_aversion": 1},
    ):
        response = api.post("/api/v1/portfolios/frontier", json={**REQUEST, **changes})
        assert response.status_code == 422
    assert prices.calls == 0


def test_benchmark_gaps_fail_without_silent_fallback(tmp_path: Path) -> None:
    prices = provider()
    prices.prices["SPY"] = prices.prices["SPY"][10:]
    response = client(tmp_path, prices).post("/api/v1/portfolios/frontier", json=REQUEST)
    assert response.status_code == 422
    assert response.json()["code"] == "MATERIAL_PRICE_GAP"


def test_shared_intersection_changes_all_model_observations(tmp_path: Path) -> None:
    prices = provider()
    for ticker in prices.prices:
        rows = prices.prices[ticker]
        rows.append((START + timedelta(days=253), rows[-1][1]))
    del prices.prices["SPY"][5]
    request = {
        **REQUEST,
        "history": {"start": START.isoformat(), "end": (START + timedelta(days=253)).isoformat()},
    }
    response = client(tmp_path, prices).post("/api/v1/portfolios/frontier", json=request)
    assert response.status_code == 200, response.text
    assert response.json()["expected_return_model"]["observations"] == 252
    assert response.json()["benchmark_expected_return_model"]["observations"] == 252
    assert ["SPY", 1] in response.json()["window"]["excluded_observations"]


class FailingFrontier:
    def generate(self, request: FrontierRequest) -> FrontierResult:
        raise OptimizationSolverError(
            "internal failure", details={"solver": "fixture", "status_code": 9}
        )


def test_solver_failure_is_structured(tmp_path: Path) -> None:
    response = client(tmp_path, provider(), frontier_generator=FailingFrontier()).post(
        "/api/v1/portfolios/frontier", json=REQUEST
    )
    assert response.status_code == 500
    assert response.json()["code"] == "OPTIMIZATION_FAILED"
    assert "internal failure" not in response.text


def test_external_failure_is_structured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prices = provider()

    def fail(*args: object, **kwargs: object) -> None:
        raise ExternalDataUnavailableError("Benchmark history unavailable")

    monkeypatch.setattr(prices, "get_price_history", fail)
    response = client(tmp_path, prices).post("/api/v1/portfolios/frontier", json=REQUEST)
    assert response.status_code == 503
    assert response.json()["code"] == "MARKET_DATA_UNAVAILABLE"


def test_environment_profile_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTFOLIO_DSS_CONSERVATIVE_FRACTION", "0.23")
    assert load_settings().frontier_profiles.fractions == (0.23, 0.5, 0.8)
    monkeypatch.setenv("PORTFOLIO_DSS_CONSERVATIVE_FRACTION", "0.9")
    with pytest.raises(ValueError, match="ordered"):
        load_settings()
