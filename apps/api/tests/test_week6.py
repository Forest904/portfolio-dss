import time
from decimal import Decimal
from itertools import product
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.application.errors import ApplicationError
from app.application.guided import personalize
from app.core.config import Settings
from app.domain import DomainValidationError, PortfolioWeights
from app.domain.frontier import PROFILE_NAMES
from app.domain.guided import PreferenceAnswers, allocate_capital, map_preferences, validate_capital
from app.infrastructure.guided_jobs import ProcessGuidedJobs, SQLiteGuidedRepository
from app.main import create_app
from tests.guided_fixtures import FixtureFactory, fixture_prices, fixture_service


@pytest.mark.parametrize("values", list(product(PROFILE_NAMES, repeat=3)))
def test_all_preferences(values: tuple[str, str, str]) -> None:
    result = map_preferences(PreferenceAnswers(*values))  # type: ignore[arg-type]
    expected = min(values, key=PROFILE_NAMES.index)
    assert result.suggested_profile == expected
    assert result.determining_answers == tuple(
        q
        for q, v in zip(("trade_off", "fluctuations", "decline"), values, strict=True)
        if v == expected
    )
    assert expected in result.explanation


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0", "0.001", "1.000"])
def test_bad_capital(value: str) -> None:
    with pytest.raises(DomainValidationError):
        validate_capital(Decimal(value))


def test_invalid_preference_and_version() -> None:
    with pytest.raises(DomainValidationError):
        map_preferences(PreferenceAnswers("unknown", "moderate", "aggressive"))  # type: ignore[arg-type]
    with pytest.raises(DomainValidationError):
        map_preferences(PreferenceAnswers(*(["moderate"] * 3)), "v2")  # type: ignore[arg-type]


def test_capital_rounding_and_permutation() -> None:
    weights = PortfolioWeights(("Z", "A", "B"), (1 / 3, 1 / 3, 1 / 3))
    result = allocate_capital(Decimal("0.02"), weights)
    assert {a.asset_id: a.amount for a in result} == {
        "Z": 0,
        "A": Decimal("0.01"),
        "B": Decimal("0.01"),
    }
    permuted = allocate_capital(Decimal("0.02"), PortfolioWeights(("B", "Z", "A"), weights.weights))
    assert {a.asset_id: a.amount for a in result} == {a.asset_id: a.amount for a in permuted}


def test_shared_snapshot_capital_and_cache(tmp_path: Path) -> None:
    repo = SQLiteGuidedRepository(tmp_path / "jobs.db")
    repo.initialize()
    stages: list[str] = []
    service = fixture_service(repository=repo)
    model = service.calculate(stages.append)
    assert model.report.holdings_capital is None
    assert stages == [
        "loading_universe",
        "loading_prices",
        "checking_coverage",
        "calculating_alternatives",
    ]
    stages.clear()
    assert service.calculate(stages.append).model_hash == model.model_hash
    assert "calculating_alternatives" not in stages
    preference = map_preferences(PreferenceAnswers("moderate", "aggressive", "moderate"))
    first = personalize(model, preference, Decimal("1234.56"))
    second = personalize(model, preference, Decimal("0.01"))
    assert first.model == second.model
    assert first.report_hash != second.report_hash
    assert {r.id for r in model.report.references} == {"equal_weight", "sp500_proxy"}
    assert not any(f.kind == "allocation_change" for f in model.report.facts)
    assert (
        model.report.expected_return_model.observations
        == model.report.benchmark_expected_return_model.observations
    )
    for alternative in first.alternatives:
        assert sum(a.amount for a in alternative.allocations) == first.capital
        assert sum(a.weight for a in alternative.allocations) == pytest.approx(1)
        assert all(0 <= a.weight <= 0.1 + 1e-8 for a in alternative.allocations)
    for p in model.report.frontier.profiles:
        point = next(v for v in model.report.frontier.points if v.id == p.point_id)
        assert point.metrics.expected_return == pytest.approx(p.target_return, abs=1e-8)
    prices = fixture_prices()
    observed, value = prices.prices["S000"][10]
    prices.prices["S000"][10] = observed, str(Decimal(value) * Decimal("1.001"))
    assert (
        fixture_service(prices=prices, repository=repo).calculate(stages.append).model_hash
        != model.model_hash
    )


def test_coverage_boundary_and_no_imputation() -> None:
    prices = fixture_prices(20)
    prices.prices["S000"] = []
    prices.prices["S001"].pop(30)
    model = fixture_service(20, prices=prices).calculate(lambda _: None)
    assert model.coverage.eligible == 18
    assert len(model.coverage.excluded) == 2
    assert model.report.window.aligned_price_observations == 300
    prices.prices["S002"].pop(40)
    with pytest.raises(ApplicationError, match="90%"):
        fixture_service(20, prices=prices).calculate(lambda _: None)


@pytest.mark.parametrize("observations", [0, 252])
def test_benchmark_required(observations: int) -> None:
    prices = fixture_prices()
    prices.prices["SPY"] = prices.prices["SPY"][:observations]
    with pytest.raises(ApplicationError):
        fixture_service(prices=prices).calculate(lambda _: None)


def test_repository_sharing_recovery_expiration(tmp_path: Path) -> None:
    now = [100000.0]
    repo = SQLiteGuidedRepository(tmp_path / "jobs.db", clock=lambda: now[0])
    repo.initialize()
    preference = map_preferences(PreferenceAnswers("moderate", "moderate", "moderate"))
    one = repo.submit("same", preference, Decimal("100"))
    two = repo.submit("same", preference, Decimal("200"))
    with repo.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM guided_runs").fetchone()[0] == 1
    assert one != two
    repo.recover()
    assert repo.get(one).error is not None
    assert repo.get(two).stage == "failed"
    now[0] += 86400
    with pytest.raises(ApplicationError):
        repo.get(one)


def test_process_api_and_validation(tmp_path: Path) -> None:
    jobs = ProcessGuidedJobs(
        SQLiteGuidedRepository(tmp_path / "jobs.db"), FixtureFactory(), lambda: "fixture"
    )
    answers = {"trade_off": "moderate", "fluctuations": "aggressive", "decline": "moderate"}
    request = {
        "version": "guided-preferences-v1",
        "answers": {"trade_off": "moderate", "fluctuations": "aggressive", "decline": "moderate"},
        "capital": "1000.01",
    }
    with TestClient(create_app(settings=Settings(tmp_path / "cache.db"), guided_jobs=jobs)) as api:
        changes_list: tuple[dict[str, object], ...] = (
            {"capital": "0"},
            {"capital": "NaN"},
            {"capital": "0.001"},
            {"version": "v2"},
            {"answers": {}},
            {"answers": {**answers, "decline": "unknown"}},
        )
        for changes in changes_list:
            assert (
                api.post("/api/v1/guided-recommendations", json={**request, **changes}).status_code
                == 422
            )
        response = api.post("/api/v1/guided-recommendations", json=request)
        assert response.status_code == 202
        job_id = response.json()["id"]
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            assert api.get("/health").status_code == 200
            result = api.get(f"/api/v1/guided-recommendations/{job_id}").json()
            if result["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)
        assert result["status"] == "completed", result
        assert result["report"]["preference"]["suggested_profile"] == "moderate"
        assert api.get("/api/v1/guided-recommendations/unknown").status_code == 404


def test_worker_timeout(tmp_path: Path) -> None:
    jobs = ProcessGuidedJobs(
        SQLiteGuidedRepository(tmp_path / "jobs.db"), FixtureFactory(), lambda: "fixture", timeout=0
    )
    jobs.start()
    try:
        job = jobs.submit(
            map_preferences(PreferenceAnswers("moderate", "moderate", "moderate")), Decimal("100")
        )
        deadline = time.monotonic() + 10
        while jobs.get(job).error is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert jobs.get(job).error.code == "JOB_TIMEOUT"  # type: ignore[union-attr]
    finally:
        jobs.close()


def test_single_supervisor_lease(tmp_path: Path) -> None:
    path = tmp_path / "jobs.db"
    first = ProcessGuidedJobs(SQLiteGuidedRepository(path), FixtureFactory(), lambda: "fixture")
    second = ProcessGuidedJobs(SQLiteGuidedRepository(path), FixtureFactory(), lambda: "fixture")
    first.start()
    try:
        with patch.object(second.repository, "initialize") as migrate:
            with pytest.raises(RuntimeError, match="one API process"):
                second.start()
            migrate.assert_not_called()
    finally:
        first.close()
    second.start()
    second.close()


def test_model_cache_expires_after_six_hours(tmp_path: Path) -> None:
    now = [100000.0]
    repository = SQLiteGuidedRepository(tmp_path / "jobs.db", clock=lambda: now[0])
    repository.initialize()
    model = fixture_service().calculate(lambda _: None)
    repository.put_model("model", model)
    now[0] += 21599
    assert repository.get_model("model") is not None
    now[0] += 1
    assert repository.get_model("model") is None
