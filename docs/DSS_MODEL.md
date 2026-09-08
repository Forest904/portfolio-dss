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

`HistoricalMeanEstimator` uses the arithmetic mean of aligned daily simple returns and annualizes
it by 252. This estimated expectation is intentionally distinct from the geometric CAGR used to
describe observed historical portfolio performance.

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

The initial implementation uses annualized sample covariance over the exact return observations
used by the expected-return estimator. The Week 4 solver is SciPy SLSQP with independently checked
long-only, budget, and optional uniform maximum-weight constraints. Risk aversion is an explicit
finite non-negative API input. Week 5 adds a separate frontier-position mapping; the guided
questionnaire remains Week 6 work.

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

Week 5 computes the efficient branch by minimizing variance at 21 return targets from the
minimum-variance portfolio's estimated return to maximum achievable return. Endpoint ties prefer
higher return at minimum variance and lower variance at maximum return. Exact profile targets are
added when they fall between chart samples.

The three named alternatives use `target = minimum_variance_return + fraction *
(maximum_return - minimum_variance_return)`, with default fractions 0.2, 0.5, and 0.8. These are
positions along the **return range**, not percentages of risk. Moderate is initially selected in
the UI; users select only the three named alternatives. A constrained or degenerate portfolio may
have one solution shared by all profiles. See ADR 0009 for numerical and comparison conventions.

Current, equal-weight, and SPY reference estimates share the same aligned observations. Historical
analysis remains a separate view and its CAGR is never used as a frontier coordinate.

The user-facing risk profile must not expose `lambda` as the primary concept.

In Week 6, a guided questionnaire will produce a preference score. The application layer maps that
score into an optimization configuration. Week 5 already exposes a typed, versioned, configurable
profile mapping without asking questionnaire questions.

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
