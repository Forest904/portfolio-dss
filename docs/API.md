# API Draft

This document describes the first stable application contracts. Endpoint names are provisional; payload responsibilities are more important than exact URLs.

## System health

### `GET /health`

The Week 1 operational endpoint is intentionally unversioned because it reports service health rather than a financial application resource.

```json
{
  "status": "ok",
  "service": "portfolio-dss-api",
  "version": "0.4.0"
}
```

The versioned universe, asset, and valuation endpoints described below are implemented in Week 2.

## Principles

- REST/JSON is sufficient for Phase A/B.
- API routes orchestrate application use cases; they do not perform financial calculations directly.
- Responses include assumptions and model metadata.
- Use async endpoints only where I/O benefits from it; do not make CPU-bound numerical work “async” by syntax alone.

## Universe

### `GET /api/v1/universes/sp500`

Returns current supported assets, the separate SPY benchmark metadata, the constituent snapshot
date, source provenance, and the current-membership assumption.

### `GET /api/v1/assets/{ticker}`

Returns normalized metadata for a current constituent. Tickers are case-insensitive at this
boundary. A ticker outside the current universe returns `ASSET_NOT_FOUND` with status 404.

## Portfolio valuation

### `POST /api/v1/portfolios/valuation`

```json
{
  "positions": [
    {"ticker": "AAPL", "quantity": "10"},
    {"ticker": "MSFT", "quantity": "4.5"}
  ],
  "as_of": "2026-09-04"
}
```

`as_of` is optional. When omitted, the service uses the latest adjusted close belonging to a
completed US market session. Weekend and holiday requests resolve to the latest common close on or
before the requested date. Decimal quantities may be numbers or strings; response monetary values
are lossless decimal strings.

The response contains:

- requested and actual valuation dates;
- total USD market value;
- normalized position quantities, prices, values, and weights;
- universe and price-source provenance, including stale-fallback status;
- a deterministic snapshot hash;
- calculation and current-universe assumptions.

## Portfolio analysis

### `POST /api/v1/portfolios/analyze`

Input concept:

```json
{
  "positions": [
    {"ticker": "AAPL", "quantity": "10"},
    {"ticker": "MSFT", "quantity": "4"}
  ],
  "history": {
    "start": "2021-01-01",
    "end": "2026-01-01"
  }
}
```

`history`, `start`, and `end` are optional. The end defaults to the latest completed US session;
the start defaults to three calendar years before the end. Analysis requires 253 common adjusted
closes (252 daily returns).

Output sections:

- end-date valuation and asset/sector concentration;
- requested and effective aligned windows plus data-quality diagnostics;
- chart-ready daily and cumulative returns for the buy-and-hold current portfolio, a buy-and-hold
  equal-dollar alternative, and the SPY benchmark proxy;
- total return, geometric CAGR, and annualized sample volatility for all three paths;
- labelled annualized sample covariance and Pearson correlation matrices;
- universe/price provenance, an analysis hash, diagnostics, and assumptions.

Undefined correlations for zero-variance assets are returned as JSON `null` and explained in
`diagnostics`. Comparisons use exactly the same timestamp intersection. API numerical values are
not presentation-rounded.

## Optimize existing portfolio universe

### `POST /api/v1/portfolios/optimize`

The implemented Week 4 endpoint accepts the current positions, a required finite non-negative
`risk_aversion`, an optional history window, and an optional uniform
`constraints.max_weight` in `(0, 1]`. `expected_return_estimator` currently defaults to and only
accepts `historical_mean`.

The response includes the current and recommended weights, allocation changes, comparable
estimated return/variance/volatility/objective values, the annualized expected-return vector and
covariance matrix, model metadata, solver diagnostics and residuals, provenance, assumptions, and
a deterministic optimization hash. These are model estimates, not the observed CAGR returned by
the analysis endpoint. The endpoint fetches only the selected assets; SPY is not an optimization
input.

Infeasible constraints return `INFEASIBLE_CONSTRAINTS` with status 422. Solver failure or failed
post-solve verification returns `OPTIMIZATION_FAILED` with status 500 and never returns target
weights. Efficient-frontier context remains a Week 5 endpoint.

## Guided portfolio builder

### `POST /api/v1/dss/recommend`

Input includes:

- capital;
- risk profile answers or normalized preference;
- optional asset/sector constraints;
- estimation configuration.

Output includes multiple alternatives, not only one portfolio.

Suggested alternatives:

- conservative;
- recommended/matched;
- aggressive.

## Efficient frontier

### `POST /api/v1/analytics/frontier`

Returns frontier points with target weights and metrics.

## Simulation

### `POST /api/v1/simulations/monte-carlo`

Input:

- portfolio weights or positions;
- horizon;
- number of simulations;
- seed;
- model assumptions.

Output:

- percentile statistics;
- probability of loss;
- terminal-return distribution summary;
- chart-ready percentile bands or sampled paths;
- assumptions.

## Backtest

### `POST /api/v1/backtests/run`

Input includes:

- universe/asset subset;
- estimator configuration;
- rebalance schedule;
- training window;
- evaluation window;
- optimization constraints.

Output includes:

- realized equity curve;
- realized return/volatility;
- benchmark comparison;
- turnover if measured;
- per-period decisions;
- diagnostics.

## Error contract

Errors should be machine-readable:

```json
{
  "code": "INSUFFICIENT_HISTORY",
  "message": "Not enough aligned history for the selected assets.",
  "details": {
    "required_observations": 252,
    "available_observations": 143
  }
}
```

Avoid returning numerical-library exceptions directly to clients.
