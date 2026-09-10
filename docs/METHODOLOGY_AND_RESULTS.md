# Methodology and Results

## Purpose and interpretation

Portfolio DSS supports decisions by comparing feasible portfolio alternatives under explicit
assumptions. It separates four kinds of evidence:

1. **Observed history:** realized prices and returns over a stated period.
2. **Estimated parameters:** expected returns and covariance calculated from an estimation window.
3. **Simulated outcomes:** distributions generated from fixed model inputs and a random seed.
4. **Out-of-sample evaluation:** decisions calculated only from information available before each
   evaluation period.

None of these is a guaranteed future value. The system does not execute trades or provide regulated
investment advice.

## Data and conventions

The production adapters obtain current S&P 500 constituents from Wikipedia and adjusted-close
history from Yahoo Finance. SPY adjusted prices serve as an explicitly labelled total-return ETF
proxy for the S&P 500. Historical membership is not reconstructed, so survivorship bias applies.

All comparable portfolios use the same effective dates and conventions:

| Convention | Value |
| --- | --- |
| Base currency | USD |
| Price field | Adjusted close |
| Return frequency | Daily |
| Return convention | Simple return |
| Annualization | 252 trading periods |
| Missing data | No imputation; timestamp intersection for portfolio analysis |
| Backtest calendar | Exact agreement with frozen SPY sessions |

Source provenance, retrieval timestamps, effective windows, exclusions, model versions, and
content hashes travel with the generated reports. See [Data](DATA.md) for adapter and cache details.

## Return and risk estimation

The optimizer consumes a stable `ExpectedReturnEstimator` contract. It does not know which concrete
model produced the expected-return vector.

### Historical arithmetic mean

`HistoricalMeanEstimator` calculates the arithmetic mean of aligned daily simple returns and
annualizes it by 252. This estimate is distinct from geometric CAGR, which describes an observed
historical portfolio path.

### Simple forecast

`SimpleForecastEstimator` calculates a normalized exponentially weighted mean with a fixed
63-observation half-life. It emphasizes recent observations while remaining transparent and
deterministic. It is a simple return-estimation alternative, not a validated price-prediction model.

### Risk estimate

`HistoricalSampleRiskEstimator` calculates the sample covariance matrix from the same aligned daily
returns and annualizes it by 252. Reported portfolio variance and volatility are:

\[
\sigma_p^2 = x^T\Sigma x
\]

\[
\sigma_p = \sqrt{x^T\Sigma x}
\]

Signed Euler contributions, \(x_i(\Sigma x)_i\), attribute modeled variance to holdings. Negative
contributions remain visible as diversification effects.

## Optimization and alternatives

The core model follows the course problem statement:

\[
\max_x \quad \mu^T x - \lambda x^T\Sigma x
\]

subject to a fully invested, long-only portfolio and an optional maximum weight:

\[
\sum_i x_i = 1, \qquad x_i \ge 0, \qquad x_i \le u
\]

SciPy SLSQP supplies the concrete solver. Every successful result includes solver diagnostics and
an independent constraint check. The efficient frontier minimizes variance across achievable return
targets. Conservative, moderate, and aggressive profiles target 20%, 50%, and 80% of the return
range between the minimum-variance and maximum-return endpoints. These fractions describe a model
choice, not probabilities or universal investor categories.

The guided questionnaire applies the deterministic `guided-preferences-v1` rule: the least
aggressive answer determines the suggested profile. Capital scales weights into illustrative USD
amounts with exact-cent conservation. It does not produce integer-share trades.

## Explanations

`decision-explanations-v1` converts typed numerical facts into three to five ranked reasons. It can
describe changes in expected return, volatility, concentration, allocations, binding caps, and risk
contributions. The wording contextualizes a joint optimization result; it does not claim that one
input caused an allocation in isolation.

## Monte Carlo uncertainty

The simulation uses a constant-weight lognormal approximation with monthly observation steps. It
accepts one-, three-, or five-year horizons; 1,000, 10,000, or 50,000 paths; and an explicit random
seed. The default is one year, 10,000 paths, seed 42.

Outputs include mean and median terminal value, percentile bands, histograms, and the empirical
probability of finishing below starting nominal capital. Parameters remain constant and weights are
continuously maintained. The bands omit parameter uncertainty and are not forecast confidence
intervals.

The frozen Week 11 guided case uses USD 10,000, three years, 10,000 paths, and seed 42. Its moderate
portfolio produces a median terminal value of USD 20,136.40 and a 0.13% simulated probability of
ending below USD 10,000. Those values describe this model and input snapshot only.

## Walk-forward evaluation

The frozen backtest covers a five-stock basket: AAPL, MSFT, JPM, JNJ, and XOM. It uses a 252-return
training window, 21-session rebalancing, USD 10,000 initial capital, risk aversion 3.0, and a 40%
maximum stock weight. Rolling and expanding variants of both return estimators are compared with a
periodically rebalanced equal-weight portfolio and SPY buy-and-hold.

At each decision date, the estimator and optimizer receive only prices available before execution.
All six strategies share 1,759 evaluation returns from 2019-01-02 through 2025-12-31. Costs, taxes,
slippage, and integer shares are excluded.

### Frozen results

| Strategy | Window | Terminal USD | Annualized return | Annualized volatility | Maximum drawdown |
| --- | --- | ---: | ---: | ---: | ---: |
| Historical mean | Rolling | 41,945.23 | 22.80% | 22.24% | 31.78% |
| Simple forecast | Rolling | 39,766.54 | 21.87% | 21.34% | 28.45% |
| Historical mean | Expanding | 38,264.57 | 21.20% | 22.51% | 30.32% |
| Simple forecast | Expanding | 41,208.38 | 22.49% | 21.42% | 28.45% |
| Equal weight | Periodic | 42,151.10 | 22.89% | 20.16% | 35.25% |
| SPY proxy | Buy and hold | 30,308.19 | 17.22% | 19.78% | 33.72% |

The selected basket and period do not establish a universally superior estimator. Historical mean
finishes ahead in the rolling comparison, while the simple forecast finishes ahead in the expanding
comparison. Equal weight has the highest terminal value in this sample, and SPY has the lowest
annualized volatility. The results support sensitivity analysis and demonstrate the evaluation
pipeline; they do not support a forecast-superiority or future-performance claim.

The canonical backtest report hash is
`eada8c9de07dab467cee7c1042859346bdc1ff7a50d87e9cca2cea80589be8f0`.

## Representative decision-support cases

The frozen Week 11 report contains three cases over 2023-01-04 through 2025-12-31:

- An 80% AAPL and 20% MSFT current portfolio. The moderate alternative reduces estimated annual
  return by 0.3 percentage points and estimated annual volatility by 0.9 percentage points relative
  to that current portfolio.
- Conservative, moderate, and aggressive allocations across five sectors, showing how target return,
  allocation, concentration, and risk contribution move together.
- A historical-versus-exponential estimator comparison at matched portfolio constraints.

The canonical case-study report hash is
`684c49f1087fb5c8c3239e953292fec92197fcf61b55a72f9e23f74a6934f9f8`.

## Reproduction

Follow the [Week 9 backtest instructions](../examples/backtest/week9/README.md) and
[Week 11 case-study instructions](../examples/case-studies/week11/README.md). Both workflows use the
checked-in frozen snapshot and write generated output outside the reference artifacts. The
[demo runbook](DEMO.md) covers the separate synthetic interactive demonstration.

See [Limitations](LIMITATIONS.md) before interpreting the results and [Testing](TESTING.md) for the
full numerical, API, browser, performance, and reproducibility evidence.
