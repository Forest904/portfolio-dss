"""Run with `uv run python -m tests.week6_benchmark`; no external data calls."""

import ctypes
import json
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from app.application.estimators import EstimatorId
from app.application.guided import GuidedModel, GuidedRecommendationService
from app.core.config import Settings
from app.infrastructure.guided_jobs import ProcessGuidedJobs, SQLiteGuidedRepository
from app.main import create_app
from tests.guided_fixtures import fixture_service


def peak_memory_bytes() -> int:
    if sys.platform == "win32":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                *[
                    (name, ctypes.c_size_t)
                    for name in (
                        "PeakWorkingSetSize",
                        "WorkingSetSize",
                        "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage",
                        "QuotaPeakNonPagedPoolUsage",
                        "QuotaNonPagedPoolUsage",
                        "PagefileUsage",
                        "PeakPagefileUsage",
                    )
                ],
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError()
        return int(counters.PeakWorkingSetSize)
    import resource

    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * (
        1 if sys.platform == "darwin" else 1024
    )


class MeasuredService(GuidedRecommendationService):
    def __init__(self, repository: SQLiteGuidedRepository) -> None:
        self.wrapped = fixture_service(500, 756, repository=repository)
        self.output = repository.path.with_suffix(".metrics.json")

    def calculate(
        self,
        progress: Callable[[str], None],
        expected_return_estimator: EstimatorId = "historical_mean",
    ) -> GuidedModel:
        started = time.monotonic()
        model = self.wrapped.calculate(progress, expected_return_estimator)
        self.output.write_text(
            json.dumps(
                {
                    "worker_seconds": time.monotonic() - started,
                    "peak_worker_memory_bytes": peak_memory_bytes(),
                }
            )
        )
        return model


@dataclass(frozen=True)
class MeasuredFactory:
    def __call__(self, repository: SQLiteGuidedRepository) -> GuidedRecommendationService:
        return MeasuredService(repository)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="week6-benchmark-") as temporary:
        path = Path(temporary) / "jobs.db"
        jobs = ProcessGuidedJobs(
            SQLiteGuidedRepository(path), MeasuredFactory(), lambda: "500-assets"
        )
        started = time.monotonic()
        health_times: list[float] = []
        stages: list[str] = []
        with TestClient(
            create_app(settings=Settings(Path(temporary) / "prices.db"), guided_jobs=jobs)
        ) as api:
            response = api.post(
                "/api/v1/guided-recommendations",
                json={
                    "version": "guided-preferences-v1",
                    "capital": "10000.00",
                    "expected_return_estimator": "simple_forecast"
                    if "--forecast" in sys.argv
                    else "historical_mean",
                    "answers": {
                        "trade_off": "moderate",
                        "fluctuations": "moderate",
                        "decline": "moderate",
                    },
                },
            )
            assert response.status_code == 202, response.text
            job_id = response.json()["id"]
            while time.monotonic() - started < 930:
                health_started = time.monotonic()
                assert api.get("/health").status_code == 200
                health_times.append(time.monotonic() - health_started)
                job = jobs.get(job_id)
                if job.stage not in stages:
                    stages.append(job.stage)
                    print(f"{time.monotonic() - started:.1f}s {job.stage}", flush=True)
                if job.status in ("completed", "failed"):
                    assert job.status == "completed", job.error
                    assert job.report is not None
                    assert job.report.model.coverage.eligible == 500
                    report = api.get(f"/api/v1/guided-recommendations/{job_id}")
                    assert report.status_code == 200
                    break
                time.sleep(0.5)
            else:
                raise AssertionError("Benchmark exceeded the job deadline")
        metrics = {
            **json.loads(path.with_suffix(".metrics.json").read_text()),
            "total_seconds": time.monotonic() - started,
            "maximum_health_seconds": max(health_times),
            "health_checks": len(health_times),
            "estimator": "simple_forecast" if "--forecast" in sys.argv else "historical_mean",
            "assets": 500,
            "prices_per_asset": 756,
            "stages_observed": stages,
        }
        print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
