# Decision Support and Mathematical Model

## Core optimization problem

The initial optimization model is mean-variance portfolio optimization:

\[
\max_x \; \mu^T x - \lambda x^T \Sigma x
\]

subject to:

\[
\sum_i x_i = 1
\]

\[
x_i \ge 0
\]

and optionally:

\[
x_i \le u_i
\]

where:

- `x` is the vector of portfolio weights;
- `mu` is the vector of expected asset returns;
- `Sigma` is the covariance matrix of asset returns;
- `lambda` controls risk aversion;
- `u_i` is an optional maximum allocation to asset `i`.

## Interpretation

The model balances two competing objectives:

1. increase expected return;
2. reduce portfolio variance.

The product should make this trade-off visible rather than hiding it behind a single number.

## Expected-return estimation

Expected returns are intentionally modeled as a replaceable input.

Initial implementations:

1. `HistoricalMeanEstimator`
2. `SimpleForecastEstimator`

The optimizer never depends on the concrete estimator.

Future estimators may include sentiment, fundamentals, macroeconomic signals, or advanced ML.

## Signal abstraction

A return-estimation model should emit a normalized object similar to:

```text
ExpectedReturnSignal
- universe_id
- asset_ids
- horizon
- annualization
- expected_returns
- model_name
- generated_at
- training_window
- confidence/quality metadata (optional)
- diagnostics
```

A future `SignalAggregator` can combine multiple compatible signals:

\[
\mu^* = \sum_{k=1}^{K} w_k \mu^{(k)}
\]

with explicit weights and compatibility checks.

This extension point is designed now; multi-source signal aggregation is not required in Phase B.

## Risk model

The initial risk model uses the sample covariance matrix of historical returns.

The risk contract must expose metadata describing:

- estimation window;
- return frequency;
- annualization factor;
- missing-data policy;
- covariance estimator name.

This allows future replacement by shrinkage or robust covariance methods.

## Efficient frontier

The system should compute multiple Pareto-efficient portfolios across risk/return preferences.

The UI should let the user compare at least:

- conservative region;
- moderate region;
- aggressive region;
- current portfolio position;
- equal-weight portfolio;
- S&P 500 benchmark where comparison is meaningful.

## Risk preference

The user-facing risk profile must not expose `lambda` as the primary concept.

A guided questionnaire produces a preference score. The application layer maps that score into an optimization configuration.

The mapping must be:

- deterministic;
- documented;
- configurable;
- testable;
- described as a modeling choice rather than a scientifically universal investor profile.

## Monte Carlo simulation

Monte Carlo is used to communicate uncertainty, not to claim a certain future path.

The simulation output should support metrics such as:

- expected terminal value;
- median terminal value;
- lower/upper percentiles;
- probability of ending below initial capital;
- distribution of terminal returns;
- selected path fan chart or percentile bands.

Simulation assumptions must be explicit and versioned.

A random seed should be accepted for reproducibility.

## Backtesting

Forecast and optimization quality should be evaluated out of sample.

Preferred design: rolling or expanding walk-forward evaluation.

At each decision date:

1. train/estimate only on information available before that date;
2. estimate `mu` and `Sigma`;
3. build a portfolio;
4. observe subsequent realized performance;
5. repeat.

This prevents look-ahead bias.

## Benchmark strategies

At minimum compare against:

- S&P 500 index;
- equal-weight portfolio over the selected universe;
- user's current portfolio when provided.

Comparisons must use matching dates, frequency, return convention, and cost assumptions.

## Explanation layer

Phase A/B explanations should be deterministic and traceable.

Examples of explainable statements include:

- an asset receives a lower weight because it contributes disproportionately to portfolio volatility;
- an asset has high expected return but is capped by concentration constraints;
- increasing risk aversion shifts allocation toward lower-volatility combinations;
- the recommended portfolio has lower expected return but a materially smaller simulated downside range;
- changing the expected-return estimator materially changes the recommended allocation.

The explanation engine must consume structured analysis facts rather than free-form hidden model reasoning.
