"""Deterministic constrained minimum-variance frontier using SciPy."""

import math

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import Bounds, LinearConstraint, minimize

from app.domain.errors import DomainValidationError, OptimizationSolverError
from app.domain.frontier import (
    PROFILE_NAMES,
    EstimatedMetrics,
    FrontierPoint,
    FrontierRequest,
    FrontierResult,
    ProfileReference,
)
from app.domain.models import PortfolioWeights
from app.domain.optimization import OPTIMIZATION_TOLERANCE, SolverDiagnostics, evaluate_portfolio
from app.infrastructure.scipy_guard import SCIPY_OPTIMIZATION_LOCK


class ScipyEfficientFrontierGenerator:
    def __init__(self, *, maximum_iterations: int = 1000) -> None:
        self._maximum_iterations = maximum_iterations

    def generate(self, request: FrontierRequest) -> FrontierResult:
        means = np.asarray(request.expected_returns.expected_returns, dtype=float)
        covariance = np.asarray(request.risk_estimate.covariance_matrix, dtype=float)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        if float(eigenvalues.min()) < -OPTIMIZATION_TOLERANCE:
            raise DomainValidationError("covariance matrix must be positive semidefinite")
        size = len(means)
        cap = request.constraints.max_weight or 1.0
        initial = np.full(size, 1.0 / size)
        scale = max(float(eigenvalues.max()), 1e-12)
        spread = float(np.ptp(means))

        def fail(reason: str, **details: object) -> None:
            raise OptimizationSolverError(reason, details={"solver": "scipy_slsqp", **details})

        def verify(raw: NDArray[np.float64], target: float | None) -> NDArray[np.float64]:
            if (
                raw.shape != (size,)
                or not np.all(np.isfinite(raw))
                or abs(float(raw.sum()) - 1) > OPTIMIZATION_TOLERANCE
                or float(raw.min()) < -OPTIMIZATION_TOLERANCE
                or float(raw.max()) > cap + OPTIMIZATION_TOLERANCE
            ):
                fail("Frontier weights failed independent verification", target_return=target)
            cleaned = np.clip(raw, 0, cap)
            cleaned /= cleaned.sum()
            if float(cleaned.max()) > cap + OPTIMIZATION_TOLERANCE or (
                target is not None and abs(float(means @ cleaned) - target) > OPTIMIZATION_TOLERANCE
            ):
                fail("Frontier target failed independent verification", target_return=target)
            return cleaned

        def solve(start: NDArray[np.float64], target: float | None) -> FrontierPoint:
            constraints = [LinearConstraint(np.ones((1, size)), 1.0, 1.0)]
            if target is not None and spread > 1e-12:
                row = (means - means.min()) / spread
                rhs = (target - float(means.min())) / spread
                constraints.append(LinearConstraint(row.reshape(1, -1), rhs, rhs))
            if size == 1 or abs(cap * size - 1) <= 1e-12 or scale <= 1e-12:
                raw = start
                status, message, iterations = 0, "Deterministic feasible solution", 0
            else:

                def objective(weights: NDArray[np.float64]) -> float:
                    return float(weights @ covariance @ weights / scale)

                def gradient(weights: NDArray[np.float64]) -> NDArray[np.float64]:
                    return np.asarray(2 * covariance @ weights / scale, dtype=float)

                with SCIPY_OPTIMIZATION_LOCK:
                    outcome = minimize(
                        objective,
                        start,
                        jac=gradient,
                        method="SLSQP",
                        bounds=Bounds(np.zeros(size), np.full(size, cap)),
                        constraints=constraints,
                        options={"ftol": 1e-12, "maxiter": self._maximum_iterations},
                    )
                if not outcome.success:
                    fail(
                        "Frontier solver did not converge",
                        target_return=target,
                        status_code=int(outcome.status),
                        message=str(outcome.message),
                    )
                raw = np.asarray(outcome.x, dtype=float)
                status, message, iterations = (
                    int(outcome.status),
                    str(outcome.message),
                    int(outcome.nit),
                )
            cleaned = verify(raw, target)
            weights = PortfolioWeights(
                request.expected_returns.asset_ids, tuple(float(w) for w in cleaned)
            )
            metrics = evaluate_portfolio(
                weights, request.expected_returns, request.risk_estimate, 0
            )
            if not all(
                math.isfinite(v)
                for v in (metrics.expected_return, metrics.variance, metrics.volatility)
            ):
                fail("Frontier metrics must be finite")
            return FrontierPoint(
                id="",
                target_return=metrics.expected_return if target is None else target,
                weights=weights,
                metrics=EstimatedMetrics(
                    metrics.expected_return, metrics.variance, metrics.volatility
                ),
                solver=SolverDiagnostics(
                    "scipy_slsqp",
                    True,
                    status,
                    message,
                    iterations,
                    abs(math.fsum(weights.weights) - 1),
                    min(weights.weights),
                    max(0.0, max(weights.weights) - cap),
                    tuple(
                        asset
                        for asset, weight in zip(weights.asset_ids, weights.weights, strict=True)
                        if request.constraints.max_weight is not None and abs(weight - cap) <= 1e-6
                    ),
                ),
            )

        minimum = solve(initial, None)
        minimum_weights = np.asarray(minimum.weights.weights)
        # All exact minimum-variance solutions differ only in the covariance nullspace.
        positive = eigenvalues > scale * 1e-12
        if not np.all(positive):
            rows = np.vstack((np.ones(size), eigenvectors[:, positive].T))
            independent: list[NDArray[np.float64]] = []
            for row in rows:
                candidate = np.vstack((*independent, row)) if independent else row.reshape(1, -1)
                if np.linalg.matrix_rank(candidate, tol=1e-10) > len(independent):
                    independent.append(np.asarray(row, dtype=float))
            constraints_matrix = np.vstack(independent)
            constraints_value = constraints_matrix @ minimum_weights

            def tie_objective(weights: NDArray[np.float64]) -> float:
                return -float(means @ weights)

            def tie_gradient(_: NDArray[np.float64]) -> NDArray[np.float64]:
                return -means

            with SCIPY_OPTIMIZATION_LOCK:
                tied = minimize(
                    tie_objective,
                    minimum_weights,
                    jac=tie_gradient,
                    method="SLSQP",
                    bounds=Bounds(np.zeros(size), np.full(size, cap)),
                    constraints=LinearConstraint(
                        constraints_matrix, constraints_value, constraints_value
                    ),
                    options={"ftol": 1e-12, "maxiter": self._maximum_iterations},
                )
            if not tied.success:
                fail("Minimum-variance tie resolution failed", message=str(tied.message))
            minimum_weights = verify(np.asarray(tied.x, dtype=float), None)
            tied_point = solve(minimum_weights, float(means @ minimum_weights))
            if abs(tied_point.metrics.variance - minimum.metrics.variance) > OPTIMIZATION_TOLERANCE:
                fail("Minimum-variance tie resolution changed risk")
            minimum = tied_point

        maximum_weights = np.zeros(size, dtype=float)
        remaining = 1.0
        for index in sorted(
            range(size), key=lambda item: (-means[item], request.expected_returns.asset_ids[item])
        ):
            allocated = min(cap, remaining)
            maximum_weights[index] = allocated
            remaining -= allocated
            if remaining <= 1e-12:
                break
        maximum_weights = verify(maximum_weights, None)
        lower, upper = minimum.metrics.expected_return, float(means @ maximum_weights)
        if upper < lower - OPTIMIZATION_TOLERANCE:
            fail("Invalid frontier endpoint ordering")
        upper = max(lower, upper)
        fractions = sorted(set([i / 20 for i in range(21)] + list(request.profiles.fractions)))
        points: list[FrontierPoint] = []
        point_for_fraction: dict[float, str] = {}
        for fraction in fractions:
            target = lower + fraction * (upper - lower)
            start = (1 - fraction) * minimum_weights + fraction * maximum_weights
            candidate = minimum if fraction == 0 or upper - lower <= 1e-12 else solve(start, target)
            if points:
                previous = points[-1].metrics
                if (
                    candidate.metrics.expected_return
                    < previous.expected_return - OPTIMIZATION_TOLERANCE
                    or candidate.metrics.variance < previous.variance - OPTIMIZATION_TOLERANCE
                ):
                    fail("Frontier ordering failed independent verification", target_return=target)
            equivalent = next(
                (
                    point
                    for point in points
                    if abs(point.metrics.expected_return - candidate.metrics.expected_return)
                    <= 1e-10
                    and abs(point.metrics.variance - candidate.metrics.variance) <= 1e-10
                ),
                None,
            )
            if equivalent is None:
                equivalent = FrontierPoint(
                    f"point-{len(points):02d}",
                    candidate.target_return,
                    candidate.weights,
                    candidate.metrics,
                    candidate.solver,
                )
                points.append(equivalent)
            point_for_fraction[fraction] = equivalent.id
        profiles = tuple(
            ProfileReference(
                name, fraction, lower + fraction * (upper - lower), point_for_fraction[fraction]
            )
            for name, fraction in zip(PROFILE_NAMES, request.profiles.fractions, strict=True)
        )
        return FrontierResult(
            tuple(points),
            profiles,
            ("All profiles coincide: no distinct efficient trade-off is available.",)
            if len(points) == 1
            else (),
        )
