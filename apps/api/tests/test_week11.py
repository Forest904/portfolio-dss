import time
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.application.backtest import FrozenSnapshot
from app.application.case_studies import CaseStudyManifest, generate_case_studies
from app.cli.case_studies import main as case_studies_main
from app.core.config import Settings
from app.infrastructure.demo import (
    DEMO_NOW,
    DemoDataProvider,
    DemoGuidedFactory,
    DemoUniverseProvider,
)
from app.infrastructure.frontier import ScipyEfficientFrontierGenerator
from app.infrastructure.guided_jobs import ProcessGuidedJobs, SQLiteGuidedRepository
from app.infrastructure.simulation import NumpySimulationEngine
from app.main import create_app

ROOT = Path(__file__).resolve().parents[3]


def test_frozen_case_studies_are_deterministic_and_cover_three_journeys() -> None:
    manifest = CaseStudyManifest.model_validate_json(
        (ROOT / "examples/case-studies/week11/manifest.json").read_text(encoding="utf-8")
    )
    snapshot = FrozenSnapshot.model_validate_json(
        (ROOT / "examples/backtest/week9/snapshot.json").read_text(encoding="utf-8")
    )

    first = generate_case_studies(
        manifest, snapshot, ScipyEfficientFrontierGenerator(), NumpySimulationEngine()
    )
    second = generate_case_studies(
        manifest, snapshot, ScipyEfficientFrontierGenerator(), NumpySimulationEngine()
    )

    assert first == second
    cases = cast(list[dict[str, Any]], first["cases"])
    assert len(cases) == 3
    assert {item["definition"]["kind"] for item in cases} == {
        "existing_portfolio",
        "guided_profiles",
        "estimator_comparison",
    }
    assert len(cast(str, first["report_hash"])) == 64


def test_case_study_cli_writes_repeatable_self_contained_reports(tmp_path: Path) -> None:
    arguments = [
        "--manifest",
        str(ROOT / "examples/case-studies/week11/manifest.json"),
        "--snapshot",
        str(ROOT / "examples/backtest/week9/snapshot.json"),
        "--output",
        str(tmp_path),
    ]
    assert case_studies_main(arguments) == 0
    first_json = (tmp_path / "report.json").read_bytes()
    first_html = (tmp_path / "report.html").read_bytes()
    assert case_studies_main(arguments) == 0
    assert (tmp_path / "report.json").read_bytes() == first_json
    assert (tmp_path / "report.html").read_bytes() == first_html
    assert b"<script src=" not in first_html
    assert b"https://" not in first_html


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"provider_timeout_seconds": 0}, "TIMEOUT"),
        ({"price_cache_ttl_hours": -1}, "TTL"),
        ({"stale_fallback_days": -1}, "STALE"),
        ({"maximum_consecutive_missing": -1}, "MISSING"),
    ],
)
def test_invalid_runtime_settings_fail_at_startup(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {"cache_path": tmp_path / "cache.sqlite3", **changes}
    with pytest.raises(ValueError, match=message):
        Settings(**values)  # type: ignore[arg-type]


def test_supported_offline_demo_serves_manual_and_guided_workflows(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs.sqlite3"
    application = create_app(
        settings=Settings(tmp_path / "cache.sqlite3"),
        universe_provider=DemoUniverseProvider(),
        market_data_provider=DemoDataProvider(),
        clock=lambda: DEMO_NOW,
        guided_jobs=ProcessGuidedJobs(
            SQLiteGuidedRepository(jobs_path), DemoGuidedFactory(), lambda: "demo-test"
        ),
    )
    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        manual = client.post(
            "/api/v1/portfolios/frontier",
            json={
                "positions": [
                    {"ticker": "AAPL", "quantity": "10"},
                    {"ticker": "MSFT", "quantity": "5"},
                ],
                "history": {"start": "2024-01-01", "end": "2025-12-31"},
                "constraints": {"max_weight": 0.5},
                "expected_return_estimator": "historical_mean",
            },
        )
        assert manual.status_code == 200, manual.text
        submitted = client.post(
            "/api/v1/guided-recommendations",
            json={
                "version": "guided-preferences-v1",
                "capital": "10000.00",
                "expected_return_estimator": "historical_mean",
                "answers": {
                    "trade_off": "moderate",
                    "fluctuations": "moderate",
                    "decline": "moderate",
                },
            },
        )
        assert submitted.status_code == 202
        job_id = submitted.json()["id"]
        for _ in range(200):
            response = client.get(f"/api/v1/guided-recommendations/{job_id}")
            if response.json()["status"] in ("completed", "failed"):
                break
            time.sleep(0.05)
        body = response.json()
        assert body["status"] == "completed", body
        assert body["report"]["model"]["coverage"]["eligible"] == 30
        assert body["report"]["model"]["price_sources"][0]["provider"] == "synthetic_demo"
