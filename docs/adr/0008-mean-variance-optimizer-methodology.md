# ADR 0008 — Mean-Variance Optimizer Methodology

- Status: Accepted
- Date: 2026-09-04

## Context

The professor's note defines the objective `max mu.T x - lambda * x.T Sigma x` but leaves
annualization, solver selection, and numerical acceptance rules open. These choices must be
explicit so recommendations are reproducible and invalid solver output is never presented.

## Decision

- Estimate expected returns as the arithmetic mean of aligned daily simple returns multiplied by
  252.
- Estimate risk as the annualized historical sample covariance over the same observations.
- Require callers to provide a finite, non-negative risk-aversion value.
- Solve with SciPy SLSQP from an equal-weight feasible starting point, with long-only, budget, and
  optional uniform maximum-weight constraints.
- Independently recompute metrics and verify constraints after convergence. A failed or invalid
  result produces an error, not a recommendation.
- Keep efficient-frontier generation outside the Week 4 optimizer contract and add it in Week 5.

## Consequences

Expected return and covariance use compatible annual units, while lambda remains an explicit
modeling choice rather than a hidden user-profile assumption. SLSQP adds a numerical dependency
and requires diagnostics and tolerances, but keeps the mathematical core replaceable through the
`PortfolioOptimizer` protocol.
