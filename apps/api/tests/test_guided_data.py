import threading
import time
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from app.application.errors import ApplicationError
from app.domain import ExternalDataUnavailableError, OptimizationSolverError
from app.domain.conventions import PriceField, ReturnFrequency
from app.domain.frontier import FrontierRequest, FrontierResult, ProfileConfiguration
from app.domain.market_data import PriceHistory
from app.infrastructure.bulk_history import BoundedBulkHistoryProvider
from app.infrastructure.guided_jobs import SQLiteGuidedRepository
from tests.guided_fixtures import fixture_prices, fixture_service
from tests.helpers import NOW, FakeMarketDataProvider


class RecordingProvider(FakeMarketDataProvider):
    def __init__(self) -> None:
        super().__init__(fixture_prices(60).prices)
        self.lock = threading.Lock()
        self.active = 0
        self.maximum_active = 0
        self.requests: list[tuple[str, ...]] = []

    def get_price_history(
        self,
        asset_ids: Sequence[str],
        start: date,
        end: date,
        frequency: ReturnFrequency,
        price_field: PriceField,
        *,
        refresh_if_stale: bool = True,
    ) -> PriceHistory:
        with self.lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            self.requests.append(tuple(asset_ids))
        try:
            time.sleep(0.005)
            if "S000" in asset_ids:
                raise ExternalDataUnavailableError("missing")
            report = super().get_price_history(asset_ids, start, end, frequency, price_field)
            return replace(report, provenance=replace(report.provenance, stale_fallback=True))
        finally:
            with self.lock:
                self.active -= 1


def test_bounded_batches_single_retry_and_stale_provenance() -> None:
    provider = RecordingProvider()
    report = BoundedBulkHistoryProvider(provider).get_bulk_history(
        tuple(f"S{i:03}" for i in range(60)), date(2023, 1, 1), NOW.date()
    )
    assert max(map(len, provider.requests)) == 25
    assert provider.maximum_active <= 2
    assert provider.requests.count(("S000",)) == 1
    assert len(report.series) == 59
    assert [f.asset_id for f in report.failures] == ["S000"]
    assert any(p.stale_fallback for p in report.provenance)


def test_profile_configuration_invalidates_cache(tmp_path: Path) -> None:
    repository = SQLiteGuidedRepository(tmp_path / "jobs.db")
    repository.initialize()
    service = fixture_service(repository=repository)
    first = service.calculate(lambda _: None)
    service._frontier._profiles = ProfileConfiguration((0.25, 0.55, 0.85))
    second = service.calculate(lambda _: None)
    assert first.model_hash != second.model_hash
    assert second.report.profile_configuration.fractions == (0.25, 0.55, 0.85)


class FailedGenerator:
    def generate(self, request: FrontierRequest) -> FrontierResult:
        raise OptimizationSolverError("failure", details={"reason": "fixture"})


def test_solver_failure_never_becomes_a_recommendation() -> None:
    service = fixture_service()
    service._frontier._generator = FailedGenerator()
    with pytest.raises(ApplicationError) as error:
        service.calculate(lambda _: None)
    assert error.value.code == "OPTIMIZATION_FAILED"
