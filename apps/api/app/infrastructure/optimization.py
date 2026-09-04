"""SciPy adapter for the long-only mean-variance optimization port."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import Bounds, LinearConstraint, minimize

from app.domain import (
    OPTIMIZATION_TOLERANCE,
    DomainValidationError,
    OptimizationRequest,
    OptimizationResult,
    OptimizationSolverError,
    PortfolioWeights,
    SolverDiagnostics,
    evaluate_portfolio,
)


class ScipyMeanVarianceOptimizer:
    """Solve the convex long-only problem with deterministic SLSQP settings."""

    def __init__(self, *, tolerance: float = 1e-10, maximum_iterations: int = 1_000) -> None:
        self._tolerance = tolerance
        self._maximum_iterations = maximum_iterations

    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        asset_ids = request.expected_returns.asset_ids
        means = np.asarray(request.expected_returns.expected_returns, dtype=float)
        covariance = np.asarray(request.risk_estimate.covariance_matrix, dtype=float)
        minimum_eigenvalue = float(np.linalg.eigvalsh(covariance).min())
        if minimum_eigenvalue < -OPTIMIZATION_TOLERANCE:
            raise DomainValidationError("covariance matrix must be positive semidefinite")

        cap = request.constraints.max_weight or 1.0
        initial = np.full(len(asset_ids), 1.0 / len(asset_ids), dtype=np.float64)

        if len(asset_ids) == 1:
            raw_weights = initial
            success, status, message, iterations = True, 0, "Single feasible asset.", 0
        else:

            def objective(weights: NDArray[np.float64]) -> float:
                return float(
                    request.risk_aversion * weights @ covariance @ weights - means @ weights
                )

            def gradient(weights: NDArray[np.float64]) -> NDArray[np.float64]:
                return np.asarray(
                    2.0 * request.risk_aversion * covariance @ weights - means,
                    dtype=np.float64,
                )

            outcome = minimize(
                objective,
                initial,
                jac=gradient,
                method="SLSQP",
                bounds=Bounds(np.zeros(len(asset_ids)), np.full(len(asset_ids), cap)),
                constraints=LinearConstraint(np.ones((1, len(asset_ids))), 1.0, 1.0),
                options={"ftol": self._tolerance, "maxiter": self._maximum_iterations},
            )
            raw_weights = np.asarray(outcome.x, dtype=float)
            success = bool(outcome.success)
            status = int(outcome.status)
            message = str(outcome.message)
            iterations = int(outcome.nit)

        raw_budget_residual = abs(float(np.sum(raw_weights)) - 1.0)
        raw_minimum = float(np.min(raw_weights))
        raw_cap_violation = max(0.0, float(np.max(raw_weights)) - cap)
        if (
            not success
            or not np.all(np.isfinite(raw_weights))
            or raw_budget_residual > OPTIMIZATION_TOLERANCE
            or raw_minimum < -OPTIMIZATION_TOLERANCE
            or raw_cap_violation > OPTIMIZATION_TOLERANCE
        ):
            raise OptimizationSolverError(
                "The optimizer did not produce a valid allocation.",
                details={
                    "solver": "scipy_slsqp",
                    "status_code": status,
                    "message": message,
                    "iterations": iterations,
                    "budget_residual": raw_budget_residual,
                    "minimum_weight": raw_minimum,
                    "max_weight_violation": raw_cap_violation,
                },
            )

        cleaned = np.clip(raw_weights, 0.0, cap)
        cleaned /= float(np.sum(cleaned))
        weights = PortfolioWeights(asset_ids, tuple(float(value) for value in cleaned))
        budget_residual = abs(math.fsum(weights.weights) - 1.0)
        minimum_weight = min(weights.weights)
        cap_violation = max(0.0, max(weights.weights) - cap)
        if (
            budget_residual > OPTIMIZATION_TOLERANCE
            or minimum_weight < 0.0
            or cap_violation > OPTIMIZATION_TOLERANCE
        ):
            raise OptimizationSolverError(
                "The optimized allocation failed independent constraint verification.",
                details={"solver": "scipy_slsqp"},
            )

        binding = (
            tuple(
                asset_id
                for asset_id, weight in zip(asset_ids, weights.weights, strict=True)
                if math.isclose(weight, cap, rel_tol=0.0, abs_tol=1e-6)
            )
            if request.constraints.max_weight is not None
            else ()
        )
        diagnostics = SolverDiagnostics(
            solver_name="scipy_slsqp",
            success=True,
            status_code=status,
            message=message,
            iterations=iterations,
            budget_residual=budget_residual,
            minimum_weight=minimum_weight,
            max_weight_violation=cap_violation,
            binding_asset_ids=binding,
        )
        return OptimizationResult(
            weights=weights,
            metrics=evaluate_portfolio(
                weights,
                request.expected_returns,
                request.risk_estimate,
                request.risk_aversion,
            ),
            constraint_status="valid",
            solver=diagnostics,
        )
