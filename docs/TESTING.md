# Testing Strategy

## Goal

The most important tests are not UI snapshots. They are tests that make financial calculations, optimization constraints, and time-series evaluation trustworthy.

## Unit tests

### Returns

Test:

- known simple-return examples;
- alignment behavior;
- missing-data policy;
- annualization.

### Portfolio valuation

Test deterministic portfolios with known prices and quantities.

### Risk

Test covariance dimensions, symmetry, asset ordering, and known small examples.

### Optimizer

For every valid result verify:

- weights sum to one within tolerance;
- weights are non-negative in Phase A/B;
- maximum-weight constraints are respected;
- reported expected return matches `mu @ x`;
- reported variance matches `x.T @ Sigma @ x`;
- solver status is valid.
- independently verified budget, lower-bound, and maximum-weight residuals are within tolerance;
- singular positive-semidefinite covariance is supported while indefinite covariance is rejected;
- solver non-convergence never produces a recommendation.

### Monte Carlo

- fixed seed produces reproducible output;
- dimensions are correct;
- zero-volatility synthetic data behaves as expected;
- percentile ordering is valid.

## Property/invariant tests

Useful invariants:

- permuting asset order consistently does not change portfolio economics;
- duplicating the same asset under different IDs must be rejected rather than silently accepted;
- equal weights sum to one;
- increasing only `lambda` should not produce a portfolio with materially higher optimized variance under the same feasible set without a documented numerical reason.

## Integration tests

- market-data adapter -> normalized price frame;
- application use case -> estimator -> risk model -> optimizer;
- FastAPI endpoint -> validated response schema;
- cached and uncached data paths produce equivalent normalized data.

## Backtest tests

Backtests must include explicit checks against look-ahead leakage.

For each rebalance date, assert that model training data ends before the evaluation interval.

Use a tiny synthetic time series where the expected result is manually understandable.

## Frontend tests

Focus on critical workflows:

- add/remove portfolio positions;
- validation feedback;
- risk-profile flow;
- comparison of current vs recommended portfolio;
- estimator switch;
- simulation rendering;
- assumptions are visible.

## Reproducibility

Store configuration with test fixtures and simulation seeds.

Do not use live external market data in unit tests.
