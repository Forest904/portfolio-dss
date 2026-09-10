"""Independent numerical checks and the stateless simulation HTTP contract."""

import json
import math
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from scipy.stats import norm

from app.api.simulation import router
from app.application.errors import ApplicationError
from app.application.simulation import PortfolioSimulationService
from app.domain.errors import DomainValidationError
from app.domain.simulation import (
    SimulationConfiguration,
    SimulationMetadata,
    SimulationNumericalError,
    SimulationPortfolio,
    SimulationRequest,
)
from app.infrastructure.guided_jobs import SQLiteGuidedRepository
from app.infrastructure.simulation import NumpySimulationEngine


def scenario(mean: float = 0.08, variance: float = 0.04, paths: int = 10000) -> SimulationRequest:
    metadata = SimulationMetadata(date(2023, 1, 3), date(2026, 1, 2), 755, "mean", "sample")
    return SimulationRequest(
        (SimulationPortfolio("current", mean, variance, metadata),),
        10000.0,
        "a" * 64,
        SimulationConfiguration(paths=paths),
    )


def test_replay_order_identity_and_seed() -> None:
    engine = NumpySimulationEngine()
    original = scenario(paths=1000)
    request = replace(
        original, portfolios=(*original.portfolios, replace(original.portfolios[0], id="moderate"))
    )
    result = engine.simulate(request)
    assert result == engine.simulate(request)
    assert result == engine.simulate(replace(request, portfolios=request.portfolios[::-1]))
    assert replace(result.portfolios[0], id="moderate") == result.portfolios[1]
    assert (
        result.portfolios
        != engine.simulate(
            replace(request, configuration=replace(request.configuration, seed=43))
        ).portfolios
    )


def test_analytical_lognormal_and_scaling() -> None:
    engine = NumpySimulationEngine()
    request = scenario(paths=50000)
    result = engine.simulate(request)
    p = result.portfolios[0]
    expected = 10000 * math.exp(0.08)
    standard_deviation = expected * math.sqrt(math.expm1(0.04))
    assert abs(p.terminal_value.mean - expected) < 5 * standard_deviation / math.sqrt(50000)
    for level, observed in zip(
        result.assumptions.percentile_levels, p.terminal_value.percentiles, strict=True
    ):
        z = float(norm.ppf(level / 100))
        analytical = 10000 * math.exp(0.06 + 0.2 * z)
        density = float(norm.pdf(z)) / (analytical * 0.2)
        quantile_se = math.sqrt(level / 100 * (1 - level / 100) / 50000) / density
        assert abs(observed - analytical) < 5 * quantile_se
    probability = float(norm.cdf(-0.06 / 0.2))
    assert abs(p.probability_of_loss - probability) < 5 * math.sqrt(
        probability * (1 - probability) / 50000
    )
    scaled = engine.simulate(replace(request, initial_capital=20000)).portfolios[0]
    assert scaled.terminal_value.mean == pytest.approx(2 * p.terminal_value.mean)
    assert scaled.terminal_return == p.terminal_return
    assert scaled.probability_of_loss == p.probability_of_loss
    assert len(p.fan) == 13
    assert p.fan[0].percentiles == (10000,) * 5
    assert len(p.histogram_counts) == 30
    assert sum(p.histogram_counts) == 50000
    assert all(
        tuple(sorted(f.percentiles)) == f.percentiles and min(f.percentiles) > 0 for f in p.fan
    )


@pytest.mark.parametrize("mean,loss", [(0.1, 0), (0, 0), (-0.1, 1)])
@pytest.mark.parametrize("years", [1, 3, 5])
def test_deterministic_zero_volatility(mean: float, loss: float, years: int) -> None:
    request = replace(scenario(mean, 0, 1000), configuration=SimulationConfiguration(years, 1000))
    result = NumpySimulationEngine().simulate(request)
    p = result.portfolios[0]
    assert p.terminal_value.mean == pytest.approx(10000 * math.exp(mean * years))
    assert p.terminal_value.standard_deviation == pytest.approx(0, abs=1e-10)
    assert p.probability_of_loss == loss
    assert len(p.fan) == years * 12 + 1
    assert sum(p.histogram_counts) == 1000
    assert len(result.histogram_edges) == 31


@pytest.mark.parametrize("mean", [1e308, -1e308])
def test_numerical_failure_is_explicit(mean: float) -> None:
    request = scenario(mean, paths=1000)
    with pytest.raises(SimulationNumericalError):
        NumpySimulationEngine().simulate(request)
    with pytest.raises(ApplicationError, match="finite simulation"):
        PortfolioSimulationService(NumpySimulationEngine()).simulate(request)


def test_domain_rejects_incompatible_inputs() -> None:
    request = scenario()
    with pytest.raises(DomainValidationError):
        replace(request, portfolios=request.portfolios * 2)
    with pytest.raises(DomainValidationError):
        replace(request, initial_capital=math.nan)
    with pytest.raises(DomainValidationError):
        replace(request.portfolios[0], annual_variance=-0.1)
    with pytest.raises(DomainValidationError):
        replace(request.portfolios[0].metadata, annualization_periods=365)
    other = replace(
        request.portfolios[0],
        id="other",
        metadata=replace(request.portfolios[0].metadata, observations=754),
    )
    with pytest.raises(DomainValidationError):
        replace(request, portfolios=(*request.portfolios, other))


def test_http_replay_without_market_or_optimizer_dependencies() -> None:
    app = FastAPI()
    app.include_router(router)
    app.state.simulation_service = PortfolioSimulationService(NumpySimulationEngine())
    client = TestClient(app)
    payload = json.loads(json.dumps({"scenario": asdict(scenario(paths=1000))}, default=str))
    response = client.post("/api/v1/portfolios/simulations", json=payload)
    assert response.status_code == 200, response.text
    assert response.json() == client.post("/api/v1/portfolios/simulations", json=payload).json()
    for seed in (True, "42", -1, 2**32, 1.5):
        payload["scenario"]["configuration"]["seed"] = seed
        assert client.post("/api/v1/portfolios/simulations", json=payload).status_code == 422
    payload["scenario"]["configuration"]["seed"] = 42
    payload["scenario"]["portfolios"] *= 7
    assert client.post("/api/v1/portfolios/simulations", json=payload).status_code == 422


def test_old_guided_cache_migration_is_idempotent(tmp_path: Path) -> None:
    repository = SQLiteGuidedRepository(tmp_path / "jobs.db")
    repository.initialize()
    with repository.connect() as db:
        db.execute("ALTER TABLE guided_runs DROP COLUMN estimator")
        db.execute("PRAGMA user_version=0")
        db.execute("INSERT INTO guided_models VALUES ('old',0,?)", (b"old-schema",))
        db.execute(
            "INSERT INTO guided_runs VALUES ('run','key',0,'completed',?,NULL)", (b"old-schema",)
        )
    repository.initialize()
    repository.initialize()
    with repository.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM guided_models").fetchone()[0] == 0
        row = db.execute("SELECT * FROM guided_runs").fetchone()
        assert row["model"] is None
        assert row["stage"] == "failed"
        assert json.loads(row["error"])["code"] == "REPORT_VERSION_CHANGED"
