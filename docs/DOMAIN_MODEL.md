# Domain Model

## Core entities and value objects

### Asset

Represents one investable instrument.

Suggested fields:

```text
Asset
- id
- ticker
- name
- exchange
- currency
- sector
- industry (optional)
- universe_memberships
```

### InvestmentUniverse

A named, versioned set of assets.

```text
InvestmentUniverse
- id
- name
- as_of_date
- asset_ids
- benchmark_asset_id
```

Initial implementation: `SP500Universe`.

### Position

```text
Position
- asset_id
- quantity
```

Invariant: quantity is non-negative in Phase A/B.

### Portfolio

```text
Portfolio
- positions
- base_currency
- valuation_time
```

A portfolio is what the user owns. It should not be confused with `PortfolioWeights`, which represent an abstract target allocation.

### PortfolioWeights

```text
PortfolioWeights
- asset_ids
- weights
```

Invariants for Phase A/B:

- all weights >= 0;
- weights sum to 1 within numerical tolerance.

### Money

Use a value object when capital or portfolio value crosses application boundaries.

```text
Money
- amount
- currency
```

Initial supported currency: USD.

### TimeHorizon

Avoid passing ambiguous integers such as `12`.

Represent horizon with unit and value, or normalized start/end dates.

### ReturnSeries

A return series must know:

- asset;
- timestamps;
- frequency;
- return convention;
- source price convention.

### ExpectedReturnSignal

Represents one model's estimate of expected returns for a compatible universe and horizon. See `DSS_MODEL.md`.

### RiskEstimate

```text
RiskEstimate
- asset_ids
- covariance_matrix
- frequency
- annualization
- estimation_window
- estimator_name
- diagnostics
```

### OptimizationRequest

```text
OptimizationRequest
- expected_returns
- risk_estimate
- risk_aversion
- constraints
```

### OptimizationResult

```text
OptimizationResult
- weights
- expected_return
- expected_volatility
- objective_value
- constraint_status
- solver_metadata
```

### SimulationRequest / SimulationResult

Simulation contracts should contain all assumptions required to reproduce a run, including seed.

### AnalysisReport

Application-level aggregate returned to the UI.

Possible sections:

```text
AnalysisReport
- portfolio_snapshot
- performance_summary
- risk_summary
- diversification_summary
- benchmark_comparison
- optimization_alternatives
- simulation_summary
- decision_facts
- assumptions
```

## Domain invariants

- Asset identifiers and ordering must be aligned across vectors and matrices.
- No optimizer input can rely on positional coincidence without explicit asset IDs.
- Annualized quantities must state the source frequency and annualization rule.
- Missing values are handled before entering optimization.
- An optimization result with violated constraints must never be presented as a valid recommendation.
- Portfolio valuation and historical analytics must state the valuation/as-of date.
