# ADR 0011 — Monte Carlo uncertainty

- Status: Accepted
- Date: 2026-09-08

## Decision

Expose a framework-independent `SimulationEngine` protocol and inject a NumPy implementation
through `PortfolioSimulationService`. The stateless simulation endpoint accepts typed, compact
scenario estimates from the displayed frontier report. It has no market-provider or optimizer
dependency. The report hash supplies provenance, not authentication of client-supplied estimates.

Simulate each portfolio's marginal geometric Brownian motion with annual drift `wᵀμ`, variance
`wᵀΣw`, and exact monthly observation increments:

`V(t + dt) = V(t) exp((μ - σ²/2)dt + σ sqrt(dt) Z)`, `dt = 1/12` year.

Annualized historical daily simple-return estimates approximate diffusion parameters; they are
neither historical CAGR nor calibrated future forecasts. Constant weights imply idealized
continuous rebalancing for all alternatives and references, including current holdings. SPY uses
its own estimates from the same historical observations. Each comparison starts with the same
capital: aligned end-date holdings value or the guided builder's entered USD amount.

Assume nominal USD, reinvested dividends, and no cash flows, fees, taxes or inflation. Parameters
remain constant; parameter-estimation uncertainty, changing regimes, fat-tail calibration and
buy-and-hold weight drift are not represented. Results compare marginal distributions, not joint
market scenarios or probabilities of outperforming another portfolio.

Default to one year, 10,000 paths and seed 42. Support 1/3/5 years, 1,000/10,000/50,000 paths and
unsigned 32-bit seeds, with at most six portfolios. Keep monthly percentile summaries and terminal
samples rather than full path matrices. Run the bounded synchronous endpoint in FastAPI's thread
pool. No recommendation jobs are started by simulation requests.

## Reproducibility and summaries

Use explicit PCG64 streams seeded by SHA-256 of the RNG contract version, seed, numerical drift
and variance. Capital, IDs, request ordering and global RNG state do not enter stream identity.
Equivalent parameters therefore share samples; this numerical coupling is not a joint model.
Sort output portfolios by ID. Return the canonical input fingerprint, result hash, full scenario,
effective configuration, assumptions, and NumPy/Python/architecture identity. Exact replay is
promised only for identical inputs and numerical implementation/environment; a seed alone cannot
freeze market-data revisions. Bump model/RNG versions whenever numerical semantics change.

Return empirical mean, population standard deviation, linear-interpolated P5/P25/P50/P75/P95,
and cumulative-return equivalents. Loss is strictly terminal value below initial capital.
The fan includes time zero. Thirty equal-width histogram bins share pooled terminal minimum and
maximum across every portfolio. When all outcomes coincide, expand the range by 1% of the value
(at least the smallest normal float). Reject nonfinite or nonpositive simulated values and
unrepresentable histogram ranges; do not clip or return partial results.

## Integration and compatibility

Both journeys use one shared uncertainty component. First opening computes all alternatives;
profile/comparator switches reuse distributions. Changed settings require Run simulation and
mark old results stale. Keep a bounded component-local cache of twelve scenario/settings results;
abort or ignore superseded requests. Simulation failure leaves the recommendation available.

`FrontierReport.holdings_capital` is an additive nullable field. Its new dataclass slot makes old
internal guided pickle blobs incompatible. Guided SQLite schema version 1 drops cached models
and changes completed runs containing old blobs to retryable `REPORT_VERSION_CHANGED` failures.
Job identities remain available to explain the required recalculation. The migration is idempotent;
the frontier configuration signature also changes to `frontier-report-v2`.

## Consequences

Portfolio-level simulation remains inexpensive for the full-universe guided builder and can
consume future compatible estimator outputs without changing the optimizer. Display the modeling
limitations beside results and expose full assumptions and replay metadata in advanced details.
Desktop/mobile visual acceptance remains required before marking Week 7 complete.
