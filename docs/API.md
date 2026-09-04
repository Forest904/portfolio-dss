# API Draft

This document describes the first stable application contracts. Endpoint names are provisional; payload responsibilities are more important than exact URLs.

## System health

### `GET /health`

The Week 1 operational endpoint is intentionally unversioned because it reports service health rather than a financial application resource.

```json
{
  "status": "ok",
  "service": "portfolio-dss-api",
  "version": "0.2.0"
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

### `POST /api/v1/portfolios/analyze` (planned for Week 3)

Input concept:

```json
{
  "positions": [
    {"ticker": "AAPL", "quantity": 10},
    {"ticker": "MSFT", "quantity": 4}
  ],
  "history": {
    "start": "2021-01-01",
    "end": "2026-01-01"
  }
}
```

Output sections:

- valuation;
- historical performance;
- risk metrics;
- correlation/diversification;
- benchmark comparison;
- assumptions.

## Optimize existing portfolio universe

### `POST /api/v1/portfolios/optimize`

Input includes:

- selected assets;
- expected-return estimator ID;
- risk preference / lambda;
- constraints;
- estimation window.

Output includes:

- target weights;
- expected return;
- expected volatility;
- efficient-frontier context;
- solver status;
- decision facts;
- assumptions.

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
