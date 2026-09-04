# Project Scope

## Delivery target

The official target is **Phase B**. Phase A is the minimum complete DSS. Phase C contains future extensions and must not be required for a successful course submission.

## Phase A — Core DSS

### Must have

- S&P 500 stock universe abstraction.
- Historical market-data ingestion through a provider interface.
- Manual portfolio input with ticker + quantity.
- Current portfolio valuation.
- Return calculations with explicit convention.
- Volatility and covariance/correlation analysis.
- Historical expected-return estimator.
- Long-only mean-variance portfolio optimization.
- Budget constraint: `sum(x) = 1`.
- Long-only constraint: `x_i >= 0`.
- Optional maximum weight per asset.
- Efficient frontier generation.
- Comparison with:
  - current portfolio;
  - optimized portfolio;
  - equal-weight portfolio;
  - S&P 500 benchmark.
- Basic deterministic explanation of recommendations.
- Interactive web UI.
- Reproducible backend tests for core calculations.

## Phase B — Target release

Everything in Phase A, plus:

- guided portfolio builder from capital + risk preference;
- risk-profile-to-optimization-preference mapping;
- Monte Carlo portfolio simulation;
- simple explainable forecast model for expected returns;
- switch between historical and forecast expected-return estimators;
- walk-forward/out-of-sample backtesting;
- direct comparison of historical-estimator vs forecast-estimator decisions;
- portfolio concentration and contribution-to-risk analysis where feasible;
- richer explanation layer;
- persistent configuration for analysis assumptions;
- polished UX suitable for a final course demonstration.

## Phase C — Future work

Potential extensions:

- short selling;
- transaction costs and turnover constraints;
- larger stock universes such as Nasdaq or broader global equities;
- sentiment signals from Reddit/X/news;
- fundamental and macroeconomic signals;
- weighted multi-signal expected-return aggregation;
- advanced ML/deep-learning forecasting;
- Black-Litterman;
- CVaR / alternative risk measures;
- robust optimization;
- multi-period optimization;
- user accounts and saved portfolios;
- live/recurrent portfolio monitoring.

## Explicit non-goals for Phase B

- high-frequency trading;
- automatic brokerage execution;
- guaranteed price prediction;
- intraday market microstructure;
- advanced deep learning;
- social-media sentiment ingestion;
- options/derivatives;
- multi-currency portfolio accounting;
- full robo-advisory regulatory suitability assessment.

## Initial simplifications

- Stocks are S&P 500 constituents.
- Long-only portfolios.
- Base currency is USD.
- Rebalancing output is expressed first as target weights; conversion to integer shares is a separate allocation step.
- Risk questionnaire is a decision-support preference input, not a regulated suitability assessment.
