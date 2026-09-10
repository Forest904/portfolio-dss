import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from app.application.estimators import EstimatorId, EstimatorRegistry
from app.domain import (
    AlignedReturnSample,
    DomainValidationError,
    ExpectedReturnSignal,
    HistoricalMeanEstimator,
    HistoricalSampleRiskEstimator,
    OptimizationConstraints,
    OptimizationRequest,
    SimpleForecastEstimator,
)
from app.domain.forecast import exponential_weights
from app.domain.frontier import FrontierRequest
from app.domain.guided import PreferenceAnswers, map_preferences
from app.infrastructure.frontier import ScipyEfficientFrontierGenerator
from app.infrastructure.guided_jobs import SQLiteGuidedRepository, calculate_worker
from app.infrastructure.optimization import ScipyMeanVarianceOptimizer
from tests.domain.test_optimization import return_sample
from tests.guided_fixtures import FixtureFactory, fixture_prices, fixture_service
from tests.test_week5_api import REQUEST, client, provider


def test_known_weighted_mean_and_diagnostics() -> None:
    sample = return_sample()
    q = 2 ** (-1 / 63)
    expected = ((q * 0.01 + 0.03) / (q + 1) * 2, (-q * 0.01 + 0.01) / (q + 1) * 2)
    signal = SimpleForecastEstimator().estimate(sample)
    assert signal.expected_returns == pytest.approx(expected)
    assert signal.asset_ids == sample.asset_ids
    assert signal.estimation_start == sample.observed_on[0]
    assert signal.estimation_end == sample.observed_on[-1]
    assert signal.observations == 2
    assert any("Short history" in d for d in signal.diagnostics)
    metadata = EstimatorRegistry(HistoricalMeanEstimator()).estimate(sample).forecast.metadata
    assert metadata.half_life_observations == 63
    assert metadata.latest_observation_weight == pytest.approx(1 / (q + 1))
    assert metadata.effective_sample_size == pytest.approx((q + 1) ** 2 / (q * q + 1))


@pytest.mark.parametrize("value", [0.0, -0.03, 0.02])
def test_constant_returns_and_annualization(value: float) -> None:
    sample = replace(return_sample(), returns=((value, value), (value, value)))
    assert SimpleForecastEstimator().estimate(sample).expected_returns == pytest.approx(
        (2 * value,) * 2
    )
    assert SimpleForecastEstimator().estimate(
        replace(sample, annualization_periods=252)
    ).expected_returns == pytest.approx((252 * value,) * 2)


def test_weights_recency_and_sample_boundary() -> None:
    weights = exponential_weights(756)
    assert math.fsum(weights) == pytest.approx(1)
    assert weights[-64] / weights[-1] == pytest.approx(0.5)
    assert all(a < b for a, b in zip(weights, weights[1:], strict=False))
    sample = return_sample()
    model = SimpleForecastEstimator()
    original = model.estimate(sample)
    reversed_sample = replace(sample, returns=tuple(tuple(reversed(row)) for row in sample.returns))
    assert original.expected_returns[0] > model.estimate(reversed_sample).expected_returns[0]
    extended = replace(
        sample,
        observed_on=(*sample.observed_on, sample.observed_on[-1] + timedelta(days=1)),
        returns=tuple((*row, 0.99) for row in sample.returns),
    )
    model.estimate(extended)
    assert model.estimate(sample) == original
    reordered = replace(
        sample, asset_ids=tuple(reversed(sample.asset_ids)), returns=tuple(reversed(sample.returns))
    )
    assert model.estimate(reordered).expected_returns == tuple(reversed(original.expected_returns))


def test_nonfinite_output_and_minimum_sample_rejected() -> None:
    with pytest.raises(DomainValidationError, match="finite"):
        SimpleForecastEstimator().estimate(
            replace(
                return_sample(), returns=((1e308, 1e308), (0.0, 0.0)), annualization_periods=252
            )
        )
    with pytest.raises(ValueError):
        exponential_weights(1)


@pytest.mark.parametrize("estimator", [HistoricalMeanEstimator(), SimpleForecastEstimator()])
def test_both_estimators_use_unchanged_solvers(
    estimator: HistoricalMeanEstimator | SimpleForecastEstimator,
) -> None:
    sample = return_sample()
    signal = estimator.estimate(sample)
    risk = HistoricalSampleRiskEstimator().estimate(sample)
    constraints = OptimizationConstraints(0.6)
    result = ScipyMeanVarianceOptimizer().optimize(
        OptimizationRequest(signal, risk, 2, constraints)
    )
    frontier = ScipyEfficientFrontierGenerator().generate(
        FrontierRequest(signal, risk, constraints)
    )
    for weights in [result.weights.weights, *(p.weights.weights for p in frontier.points)]:
        assert sum(weights) == pytest.approx(1)
        assert min(weights) >= 0
        assert max(weights) <= 0.6 + 1e-8


@pytest.mark.parametrize("endpoint", ["frontier", "optimize"])
def test_api_selection_comparison_and_shared_snapshot(tmp_path: Path, endpoint: str) -> None:
    prices = provider()
    api = client(tmp_path, prices)
    request = {**REQUEST, **({"risk_aversion": 2} if endpoint == "optimize" else {})}
    historical = api.post(f"/api/v1/portfolios/{endpoint}", json=request).json()
    response = api.post(
        f"/api/v1/portfolios/{endpoint}",
        json={**request, "expected_return_estimator": "simple_forecast"},
    )
    assert response.status_code == 200, response.text
    forecast = response.json()
    comparison = forecast["expected_return_comparison"]
    assert comparison["selected_estimator"] == "simple_forecast"
    assert historical["expected_return_comparison"]["selected_estimator"] == "historical_mean"
    assert historical["risk_model"] == forecast["risk_model"]
    assert prices.calls == 2
    assert prices.requested_asset_ids == [("AAPL", "MSFT", "SPY")] * 2
    for pair in [comparison["assets"], comparison["benchmark"]]:
        for model in pair.values():
            assert (
                model["signal"]["estimation_start"]
                == comparison["assets"]["historical"]["signal"]["estimation_start"]
            )
            assert model["signal"]["observations"] == 252
    for row in comparison["portfolios"]:
        assert row["difference"] == pytest.approx(
            row["forecast_expected_return"] - row["historical_expected_return"]
        )
        if row["id"] == "equal_weight":
            for model in ("historical", "forecast"):
                assert row[f"{model}_expected_return"] == pytest.approx(
                    sum(comparison["assets"][model]["signal"]["expected_returns"]) / 2
                )
    assert (
        api.post(
            f"/api/v1/portfolios/{endpoint}",
            json={**request, "expected_return_estimator": "unknown"},
        ).status_code
        == 422
    )


def test_concurrent_selection_and_injected_registry(tmp_path: Path) -> None:
    api = client(
        tmp_path,
        provider(),
        estimator_registry=EstimatorRegistry(HistoricalMeanEstimator(), SimpleForecastEstimator()),
    )
    selections: list[EstimatorId] = ["historical_mean", "simple_forecast"] * 2

    def run(selection: EstimatorId) -> str:
        response = api.post(
            "/api/v1/portfolios/frontier", json={**REQUEST, "expected_return_estimator": selection}
        )
        assert response.status_code == 200
        return str(response.json()["expected_return_comparison"]["selected_estimator"])

    with ThreadPoolExecutor(4) as pool:
        assert list(pool.map(run, selections)) == selections


def test_guided_cache_separation_worker_and_one_solver(tmp_path: Path) -> None:
    repository = SQLiteGuidedRepository(tmp_path / "jobs.db")
    repository.initialize()
    prices = fixture_prices()
    service = fixture_service(prices=prices, repository=repository)
    original = ScipyEfficientFrontierGenerator.generate
    with patch.object(
        ScipyEfficientFrontierGenerator, "generate", autospec=True, side_effect=original
    ) as solve:
        forecast = service.calculate(lambda _: None, "simple_forecast")
        first_fetches = prices.calls
        assert solve.call_count == 1
        assert forecast.report.expected_return_comparison is not None
        assert len(forecast.report.expected_return_comparison.portfolios) == 5
        assert (
            service.calculate(lambda _: None, "simple_forecast").model_hash == forecast.model_hash
        )
        assert solve.call_count == 1
        historical = service.calculate(lambda _: None)
        assert solve.call_count == 2
        assert historical.model_hash != forecast.model_hash
        assert prices.calls == first_fetches * 3
    preference = map_preferences(PreferenceAnswers("moderate", "moderate", "moderate"))
    historical_job = repository.submit("same", preference, Decimal(100))
    forecast_job = repository.submit("same", preference, Decimal(100), "simple_forecast")
    with repository.connect() as db:
        run = db.execute("SELECT run_id FROM guided_jobs WHERE id=?", (forecast_job,)).fetchone()[0]
        assert db.execute("SELECT COUNT(*) FROM guided_runs").fetchone()[0] == 2
    calculate_worker(repository.path, run, FixtureFactory())
    report = repository.get(forecast_job).report
    assert report is not None
    assert report.model.report.expected_return_model.estimator_name == "simple_exponential_forecast"
    assert repository.get(historical_job).status == "queued"
    repository.initialize()
    assert repository.get(forecast_job).report == report


def test_version_one_migration(tmp_path: Path) -> None:
    repository = SQLiteGuidedRepository(tmp_path / "jobs.db")
    repository.initialize()
    with repository.connect() as db:
        db.execute("ALTER TABLE guided_runs DROP COLUMN estimator")
        db.execute("PRAGMA user_version=1")
        db.execute("INSERT INTO guided_runs VALUES ('r','k',0,'completed',?,NULL)", (b"old",))
        db.execute("INSERT INTO guided_models VALUES ('m',0,?)", (b"old",))
    repository.initialize()
    repository.initialize()
    with repository.connect() as db:
        row = db.execute("SELECT * FROM guided_runs").fetchone()
        assert row["estimator"] == "historical_mean"
        assert row["model"] is None and row["stage"] == "failed"
        assert "REPORT_VERSION_CHANGED" in row["error"]
        assert db.execute("SELECT COUNT(*) FROM guided_models").fetchone()[0] == 0


def test_legacy_injection_and_configuration_identity(tmp_path: Path) -> None:
    class ConstantEstimator:
        def estimate(self, sample: AlignedReturnSample) -> ExpectedReturnSignal:
            return replace(
                HistoricalMeanEstimator().estimate(sample),
                expected_returns=(0.07,) * len(sample.asset_ids),
                estimator_name="constant_fixture",
            )

    registry = EstimatorRegistry(ConstantEstimator(), historical_version="constant-7pct-v1")
    different = EstimatorRegistry(ConstantEstimator(), historical_version="constant-8pct-v1")
    assert registry.identity("historical_mean") != different.identity("historical_mean")
    api = client(tmp_path, provider(), expected_return_estimator=ConstantEstimator())
    response = api.post("/api/v1/portfolios/frontier", json=REQUEST)
    assert response.status_code == 200, response.text
    assert response.json()["expected_return_model"]["expected_returns"] == [0.07, 0.07]


def test_estimator_failure_is_visible_without_fallback(tmp_path: Path) -> None:
    class FailingEstimator:
        def estimate(self, sample: AlignedReturnSample) -> ExpectedReturnSignal:
            raise DomainValidationError("Nonfinite model")

    api = client(
        tmp_path,
        provider(),
        estimator_registry=EstimatorRegistry(HistoricalMeanEstimator(), FailingEstimator()),
    )
    response = api.post(
        "/api/v1/portfolios/frontier",
        json={**REQUEST, "expected_return_estimator": "simple_forecast"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "ESTIMATION_NUMERICAL_FAILURE"


def test_guided_selector_validation(tmp_path: Path) -> None:
    api = client(tmp_path, provider())
    response = api.post(
        "/api/v1/guided-recommendations",
        json={
            "version": "guided-preferences-v1",
            "capital": "10000",
            "answers": {"trade_off": "moderate", "fluctuations": "moderate", "decline": "moderate"},
            "expected_return_estimator": "unknown",
        },
    )
    assert response.status_code == 422
