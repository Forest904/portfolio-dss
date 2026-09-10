# 12-Week Roadmap

## Delivery philosophy

Phase B is the target. Every milestone should leave the repository in a working state. Advanced features are added only after the core DSS is correct and testable.

## Week 1 — Foundations and project contract

**Goal:** freeze conventions and create the technical skeleton.

**State:** complete

Deliverables:

- repository structure;
- backend/frontend bootstraps;
- core domain types;
- S&P 500 universe abstraction;
- financial convention configuration;
- first ADRs;
- CI for linting/tests.

Exit criteria:

- API and web app run locally;
- one health endpoint;
- tests run in CI;
- domain layer has no framework dependencies.

## Week 2 — Market data and portfolio valuation

**Goal:** reliable data path.

**State:** complete

Deliverables:

- first `MarketDataProvider` adapter;
- S&P 500 constituent loader;
- data validation/alignment;
- local cache;
- ticker + quantity portfolio input model;
- current portfolio valuation.

Exit criteria:

- user can submit a small valid portfolio to API and receive a reproducible valuation snapshot.

## Week 3 — Historical analytics

**Goal:** analyze current portfolio.

**State:** complete

Deliverables:

- return series;
- annualized return/volatility;
- covariance and correlation;
- concentration metrics;
- S&P 500 comparison;
- equal-weight comparison;
- analysis API response.

Exit criteria:

- current portfolio analysis is numerically tested and viewable in a basic UI.

## Week 4 — Mean-variance optimizer

**Goal:** implement the mathematical core from the professor's note.

**State:** complete

Deliverables:

- `HistoricalMeanEstimator`;
- `RiskEstimator`;
- `PortfolioOptimizer`;
- long-only and budget constraints;
- optional max-weight constraint;
- solver diagnostics;
- current vs optimized comparison.

Exit criteria:

- optimizer invariants are tested;
- API returns a valid recommended allocation.

## Week 5 — Efficient frontier and decision alternatives

**Goal:** make trade-offs visible.

**State:** complete; automated interaction and desktop/mobile visual checks verified.

The frontier API and web workspace use configurable 20%/50%/80% return-range profiles, shared
current/equal-weight/SPY estimates, and deterministic decision facts. See ADR 0009 and
`docs/TESTING.md` for methodology and validation.

Deliverables:

- efficient frontier;
- conservative/moderate/aggressive alternatives;
- risk-preference configuration;
- frontier UI;
- deterministic decision facts.

Exit criteria:

- user can move between alternatives and see allocation/risk/return changes.

## Week 6 — Guided DSS flow

**Goal:** make the system usable by a non-expert.

**State:** complete. Guided construction, full-universe eligibility screening, background jobs,
USD allocation, and desktop/mobile validation are implemented. The deterministic 500-stock
background benchmark completed in 421.8 seconds; see ADR 0010 and `docs/TESTING.md`.

Deliverables:

- short risk/preference questionnaire;
- capital input;
- mapping preference -> optimizer configuration;
- guided recommendation flow;
- clear assumptions and explanatory copy.

Exit criteria:

- user can reach a recommendation without manually configuring mathematical parameters.

## Week 7 — Monte Carlo uncertainty

**Goal:** represent possible outcomes as distributions.

**State:** complete. Numerical/API/UI automation, performance validation, and attached-Chrome
desktop/mobile visual acceptance passed. Mobile chart readability and keyboard scrolling were
fixed and visually rechecked on 2026-09-09; see ADR 0011 and `docs/TESTING.md`.

Deliverables:

- `SimulationEngine`;
- reproducible random seed;
- terminal distribution metrics;
- probability-of-loss metric;
- percentile/fan visualization;
- current vs recommended simulation comparison.

Exit criteria:

- simulation assumptions are displayed and results are reproducible.

## Week 8 — Simple explainable forecast

**Goal:** add a second expected-return model without changing the optimizer.

**State:** complete. Fixed 63-observation exponential forecasting, both workflow selectors,
fixed-weight comparisons, diagnostics, and guided-job migration are implemented. Numerical/API/UI
checks, the 500-stock forecast benchmark, and desktop/mobile visual acceptance passed on
2026-09-09; see ADR 0012 and `docs/TESTING.md`.

Deliverables:

- choose and document a simple forecast model;
- `SimpleForecastEstimator` implementation;
- estimator diagnostics;
- UI/API estimator selector;
- historical vs forecast expected-return comparison.

Exit criteria:

- optimizer runs unchanged with either estimator contract.

## Week 9 — Walk-forward backtesting

**Goal:** evaluate decisions out of sample.

**State:** complete. The offline snapshot/replay CLI, rolling and expanding strategies,
strict execution timing, and self-contained HTML/JSON report are implemented. The frozen
2019–2025 comparison includes all six series on 1,759 identical evaluation returns. Backend
checks and desktop/mobile report inspection passed on 2026-09-10; see ADR 0013,
`docs/TESTING.md`, and `examples/backtest/week9/README.md`.

Deliverables:

- `BacktestEngine`;
- rolling/expanding training windows;
- no-look-ahead tests;
- historical-estimator strategy;
- forecast-estimator strategy;
- S&P 500 and equal-weight baselines.

Exit criteria:

- one reproducible backtest report compares all strategies on the same period.

## Week 10 — Decision-support explanations and UX polish

**Goal:** turn analytics into support for action.

**State:** complete. Deterministic, fact-backed explanations, signed portfolio risk attribution,
baseline-relative allocation rationale, focused result views, advanced evidence panels, chart and
state polish, and inline accessible validation are implemented. Backend/frontend checks and
desktop/mobile browser acceptance passed on 2026-09-10; see ADR 0014 and `docs/TESTING.md`.

Deliverables:

- structured decision facts;
- rule-based explanation engine;
- portfolio-change rationale;
- advanced-details panels;
- clearer charts, empty states, and validation.

Exit criteria:

- a non-expert can understand why the recommended portfolio differs from the current one.

## Week 11 — Hardening and evaluation

**Goal:** reliability and defensible results.

Deliverables:

- broader automated tests;
- edge-case handling;
- performance profiling;
- caching improvements;
- documented limitations;
- selected case studies.

Exit criteria:

- core demo does not depend on fragile notebook steps or manual data preparation.

## Week 12 — Submission package

**Goal:** present a coherent DSS project.

Deliverables:

- final README;
- architecture diagrams;
- methodology/results documentation;
- demo dataset/configuration;
- presentation/demo script;
- future-work section;
- tagged release.

Exit criteria:

- clean install/run path;
- reproducible demo;
- Phase B complete or clearly documented with any remaining limitation.

## Stretch-goal rule

Do not start Phase C unless Weeks 1–9 are stable.

Priority order for spare time:

1. better explanation and UX;
2. stronger backtesting/evaluation;
3. contribution-to-risk analytics;
4. configurable multi-signal aggregation prototype;
5. only then new data sources or advanced models.
