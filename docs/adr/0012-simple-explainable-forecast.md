# ADR 0012 ? Simple explainable forecast

- Status: Accepted
- Date: 2026-09-09

## Decision

Add `SimpleForecastEstimator` behind the unchanged
`ExpectedReturnEstimator.estimate(AlignedReturnSample) -> ExpectedReturnSignal` protocol.
Keep the mean-variance optimizer, efficient-frontier generator, risk estimator and simulation
engine unchanged. Historical mean remains the default in both user journeys.

For the n aligned daily simple returns, let q = 2^(-1/63) and normalize weights
`a[t] = q^(n-t) / sum(q^(n-j), j=1..n)`. The asset signal is
`annualization_periods * sum(a[t] * r[t])`. The fixed half-life is 63 trading observations,
not calendar days. All observations remain in the sample. Normalization avoids special weight
on the first observation from recursive initialization. There is no fitting, parameter search,
clipping, missing-data filling, or fallback to a different estimator.

This finite-sample exponentially weighted mean adopts the flat future-mean assumption of
[simple exponential smoothing](https://otexts.com/fpp3/ses.html), while explicitly choosing
normalized weights rather than optimizing an initial level. The choice is an explainable
baseline, not evidence of superior stock-return prediction. Week 9 supplies walk-forward
out-of-sample evaluation. An annualized arithmetic daily mean is not CAGR, a price forecast,
or a guaranteed one-year return. Extending the mean into multi-year simulations assumes it
remains constant; parameter uncertainty and regime changes remain excluded.

## Contracts and comparisons

The application registry owns estimator composition and explicit version identities. Existing
historical-estimator injection remains supported; a registry can also inject the forecast and
supply version identities for custom configurations. No request mutates a shared estimator choice.
The HTTP selector is `expected_return_estimator`, accepting `historical_mean` or `simple_forecast`,
with historical as the omitted-field default and 422 for other values.

Optimization, frontier and guided reports include `expected_return_comparison`: both asset
signals, benchmark signals, typed model metadata, selected estimator and portfolio rows.
Metadata includes weighting method, model version, training dates, observation count, half-life,
effective sample size `1/sum(a?)` and latest-observation weight. Fewer than 63 observations
produce a warning; the existing minimum of two remains valid. Nonfinite estimates fail visibly.

Both models use exactly the same sample; SPY uses the same aligned dates and conventions.
The optimization endpoint now requests SPY alongside holdings in its single price fetch so its
new benchmark comparison is comparable. This adds a benchmark-data dependency and can narrow
the common window when SPY observations are missing; no missing values are filled.

Only the selected signal drives one optimization/frontier calculation. Evaluate fixed weights
under both models for current holdings where supplied, recommended weights or the three profiles,
equal weight and SPY. Differences are forecast minus historical annualized return fractions;
the UI multiplies them by 100 for percentage points/year. No second allocation is optimized.
Observed historical analytics stay unchanged. Simulations consume selected-model means and
provenance through the existing scenario contract.

## Guided jobs, compatibility and UI

Persist estimator selection on guided runs, pass it into worker calculation, and distinguish
run deduplication, model-cache keys and report hashes by selection and versioned configuration.
SQLite schema version 2 adds `guided_runs.estimator` with a historical default, clears old
model caches, and converts completed incompatible reports to retryable `REPORT_VERSION_CHANGED`
failures while retaining job identities. Migration is idempotent and runs only after acquiring
the single-supervisor lease, so a competing process cannot migrate an active database. Queued/interrupted work follows
the existing restart-recovery policy. No external database service is added.

Both input journeys expose an accessible selector. Changing it invalidates pending responses
and marks old recommendations/simulations stale; recalculation uses the existing submit action.
Displayed values retain their calculated model identity. Simulation requests are blocked until
recommendations are refreshed. Both model columns use the same weights; diagnostics and asset
rows are expandable, with 25 assets per page for the full guided universe.

## Validation

See `docs/TESTING.md` for numerical, integration, UI, full-universe performance and browser
acceptance evidence. No out-of-sample accuracy claim is part of Week 8.
