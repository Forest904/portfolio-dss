"""Deterministic Week 11 profiling; no external data or pass/fail timing budgets."""

from __future__ import annotations

import argparse
import cProfile
import json
import platform
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Any

from app.application.backtest import BacktestSettings, FrozenSnapshot, build_engine
from app.application.case_studies import CaseStudyManifest, generate_case_studies
from app.domain.simulation import (
    SimulationConfiguration,
    SimulationMetadata,
    SimulationPortfolio,
    SimulationRequest,
)
from app.infrastructure.cache import SQLiteCache
from app.infrastructure.frontier import ScipyEfficientFrontierGenerator
from app.infrastructure.optimization import ScipyMeanVarianceOptimizer
from app.infrastructure.simulation import NumpySimulationEngine


def measure[T](operation: Callable[[], T]) -> tuple[dict[str, object], T]:
    tracemalloc.start()
    started = time.perf_counter()
    result = operation()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"elapsed_seconds": elapsed, "python_peak_bytes": peak}, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    manifest = CaseStudyManifest.model_validate_json(
        (root / "examples/case-studies/week11/manifest.json").read_text(encoding="utf-8")
    )
    snapshot = FrozenSnapshot.model_validate_json(
        (root / "examples/backtest/week9/snapshot.json").read_text(encoding="utf-8")
    )
    settings = BacktestSettings.model_validate_json(
        (root / "examples/backtest/week9/config.json").read_text(encoding="utf-8")
    )
    profile = cProfile.Profile()
    profile.enable()
    cases_metrics, cases = measure(
        lambda: generate_case_studies(
            manifest, snapshot, ScipyEfficientFrontierGenerator(), NumpySimulationEngine()
        )
    )
    prices = snapshot.validate_for(settings.to_domain())
    backtest_metrics, backtest = measure(
        lambda: build_engine(ScipyMeanVarianceOptimizer(), "week11-profile").run(
            settings.to_domain(), prices
        )
    )
    metadata = SimulationMetadata(
        date(2023, 1, 1), date(2025, 12, 31), 756, "profile", "sample_covariance"
    )
    simulation_request = SimulationRequest(
        tuple(
            SimulationPortfolio(
                f"portfolio-{index}",
                0.02 + index * 0.02,
                0.01 + index * 0.01,
                metadata,
            )
            for index in range(6)
        ),
        10_000,
        "0" * 64,
        SimulationConfiguration(5, 50_000, 42),
    )
    simulation_metrics, simulation = measure(
        lambda: NumpySimulationEngine().simulate(simulation_request)
    )
    with tempfile.TemporaryDirectory(prefix="week11-cache-") as temporary:
        cache = SQLiteCache(Path(temporary) / "prices.sqlite3")
        now = datetime(2026, 9, 10, tzinfo=UTC)

        def exercise_cache() -> None:
            for index in range(30):
                asset = f"S{index:03}"
                cache.put_price_series(
                    "profile",
                    asset,
                    "daily",
                    "adjusted_close",
                    date(2023, 1, 1),
                    date(2025, 12, 31),
                    json.dumps({"asset_id": asset}),
                    now,
                )
            for index in range(30):
                assert (
                    cache.get_covering_price_series(
                        "profile",
                        f"S{index:03}",
                        "daily",
                        "adjusted_close",
                        date(2024, 1, 1),
                        date(2025, 1, 1),
                        not_before=now - timedelta(hours=1),
                    )
                    is not None
                )

        cache_metrics, _ = measure(exercise_cache)
    profile.disable()
    payload: dict[str, Any] = {
        "policy": "measurement-only; values are local observations, not service guarantees",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "dependencies": {name: version(name) for name in ("numpy", "scipy", "pandas")},
        "case_studies": {**cases_metrics, "result_hash": cases["report_hash"]},
        "backtest": {**backtest_metrics, "strategies": len(backtest.strategies)},
        "simulation": {**simulation_metrics, "result_hash": simulation.result_hash},
        "cache_covering_snapshots": {**cache_metrics, **asdict(cache.metrics)},
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    if args.profile:
        args.profile.parent.mkdir(parents=True, exist_ok=True)
        profile.dump_stats(args.profile)
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
