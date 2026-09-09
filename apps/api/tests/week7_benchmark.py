"""Offline benchmark: uv run python -m tests.week7_benchmark."""

import json
import platform
import time
from dataclasses import replace

from app.domain.simulation import SimulationConfiguration
from app.infrastructure.simulation import NumpySimulationEngine
from tests.test_simulation import scenario
from tests.week6_benchmark import peak_memory_bytes

if __name__ == "__main__":
    base = scenario()
    request = replace(
        base,
        configuration=SimulationConfiguration(5, 50000, 42),
        portfolios=tuple(
            replace(
                base.portfolios[0],
                id=f"portfolio-{i}",
                annual_mean=0.02 + i * 0.02,
                annual_variance=0.01 + i * 0.01,
            )
            for i in range(6)
        ),
    )
    started = time.perf_counter()
    result = NumpySimulationEngine().simulate(request)
    print(
        json.dumps(
            {
                "elapsed_seconds": time.perf_counter() - started,
                "peak_process_memory_bytes": peak_memory_bytes(),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "environment": result.numerical_environment,
                "result_hash": result.result_hash,
            },
            indent=2,
        )
    )
