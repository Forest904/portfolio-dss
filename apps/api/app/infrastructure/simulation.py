"""Bounded Monte Carlo implementation; each portfolio has a reproducible marginal stream."""

import hashlib
import json
import platform
from dataclasses import asdict, replace

import numpy as np
from numpy.typing import NDArray

from app.domain.simulation import (
    DistributionMetrics,
    FanPoint,
    PortfolioSimulation,
    SimulationAssumptions,
    SimulationNumericalError,
    SimulationRequest,
    SimulationResult,
)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


class NumpySimulationEngine:
    def simulate(self, request: SimulationRequest) -> SimulationResult:
        assumptions = SimulationAssumptions()
        configuration = request.configuration
        ordered = replace(request, portfolios=tuple(sorted(request.portfolios, key=lambda p: p.id)))
        environment = (
            f"NumPy {np.__version__}; Python {platform.python_version()}; {platform.machine()}"
        )
        fingerprint = digest((asdict(ordered), asdict(assumptions), environment))
        terminals: list[NDArray[np.float64]] = []
        results: list[PortfolioSimulation] = []
        levels = assumptions.percentile_levels
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                for portfolio in ordered.portfolios:
                    # Exclude capital, ordering and labels so equivalent economics share samples.
                    key = digest(
                        (
                            assumptions.rng_version,
                            configuration.seed,
                            float(portfolio.annual_mean) + 0.0,
                            float(portfolio.annual_variance) + 0.0,
                        )
                    )
                    rng = np.random.Generator(np.random.PCG64(int(key, 16)))
                    logs = np.zeros(configuration.paths, dtype=np.float64)
                    fan = [FanPoint(0, (request.initial_capital,) * len(levels))]
                    drift = (portfolio.annual_mean - portfolio.annual_variance / 2) / 12
                    scale = np.sqrt(portfolio.annual_variance / 12)
                    values = np.full(configuration.paths, request.initial_capital)
                    for month in range(1, configuration.horizon_years * 12 + 1):
                        logs += drift + scale * rng.standard_normal(configuration.paths)
                        values = request.initial_capital * np.exp(logs)
                        if not np.all(np.isfinite(values)) or np.any(values <= 0):
                            raise SimulationNumericalError("Values overflowed or underflowed")
                        fan.append(
                            FanPoint(
                                month,
                                tuple(
                                    float(v) for v in np.percentile(values, levels, method="linear")
                                ),
                            )
                        )
                    percentiles = fan[-1].percentiles
                    mean, std = float(np.mean(values)), float(np.std(values, ddof=0))
                    value_metrics = DistributionMetrics(mean, std, percentiles)
                    return_metrics = DistributionMetrics(
                        mean / request.initial_capital - 1,
                        std / request.initial_capital,
                        tuple(v / request.initial_capital - 1 for v in percentiles),
                    )
                    results.append(
                        PortfolioSimulation(
                            portfolio.id,
                            value_metrics,
                            return_metrics,
                            float(np.count_nonzero(values < request.initial_capital) / len(values)),
                            tuple(fan),
                            (),
                        )
                    )
                    terminals.append(values)
                low = min(float(v.min()) for v in terminals)
                high = max(float(v.max()) for v in terminals)
                if low == high:
                    padding = max(abs(low) * 0.01, np.finfo(float).tiny)
                    low, high = max(0.0, low - padding), high + padding
                edges = np.linspace(low, high, 31)
                if not np.all(np.isfinite(edges)) or not np.all(np.diff(edges) > 0):
                    raise SimulationNumericalError("Histogram range is not representable")
                results = [
                    replace(
                        result,
                        histogram_counts=tuple(
                            int(v) for v in np.histogram(terminal, bins=edges)[0]
                        ),
                    )
                    for result, terminal in zip(results, terminals, strict=True)
                ]
                report = SimulationResult(
                    ordered,
                    assumptions,
                    environment,
                    tuple(results),
                    tuple(float(v) for v in edges),
                    fingerprint,
                    "",
                )
                return replace(report, result_hash=digest(asdict(report)))
        except (FloatingPointError, OverflowError, ValueError) as exc:
            raise SimulationNumericalError(
                "Simulation produced an unrepresentable outcome"
            ) from exc
