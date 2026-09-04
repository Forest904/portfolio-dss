# Data Strategy

## Initial data domain

Phase A/B operates on:

- S&P 500 constituents;
- S&P 500 index benchmark;
- daily historical market prices.

## Provider abstraction

Market data must be accessed through `MarketDataProvider`.

The first implementation uses Yahoo Finance through `yfinance`. The infrastructure adapter requests
daily data with automatic OHLC adjustment disabled and selects the adjusted-close column explicitly.
No analytical model depends on pandas or yfinance.

## Universe versioning

The S&P 500 is not a permanent list of the same 500 companies.

The system should attach an `as_of_date` to the universe definition.

Wikipedia supplies the current constituent snapshot. Historical constituents are not reconstructed;
valuation responses disclose this current-membership assumption and its survivorship-bias limitation.

## Benchmark convention

The initial S&P 500 benchmark is `SPY`, using adjusted-close returns. It is an ETF-based total-return proxy and must be labelled as such; it is not the official S&P 500 price index. Benchmark metadata is separate from S&P 500 constituent membership, so `SPY` is not required to appear among universe constituents.

## Price convention

Choose and document one default price series for return calculations.

Recommended initial convention:

- daily adjusted close where available;
- daily simple returns;
- annualization based on 252 trading periods;
- no missing-value imputation;
- timestamp-intersection alignment, followed by explicit insufficient-history and material-gap validation.

Do not hard-code this knowledge across modules. Put conventions in one configuration/model object.

## Data pipeline

```text
Provider
  ↓
Raw price data
  ↓
Validation
  ↓
Calendar/alignment policy
  ↓
Return transformation
  ↓
Analytics/model inputs
```

## Validation checks

- unknown ticker;
- duplicate ticker;
- missing date range;
- insufficient history;
- long missing-data gaps;
- non-monotonic timestamps;
- duplicated timestamps;
- incompatible currencies;
- stale valuation data.

## Caching

Development uses a SQLite read-through cache keyed by:

- provider;
- asset;
- date range;
- frequency;
- price convention.

Cache metadata should include retrieval time.

Normalized payloads include their retrieval time and SHA-256 content hash. Explicit historical
requests reuse their cached snapshot. Current requests refresh after their TTL; if refresh fails, a
cached result may be returned only inside the configured seven-day bound and is marked as a stale
fallback. The cache is a performance/reproducibility aid, not the source of business truth.

## Reproducibility

Every generated analysis should be traceable to:

- universe version/as-of date;
- data provider;
- data range;
- return convention;
- estimator configuration;
- risk model configuration;
- optimizer configuration;
- simulation seed when applicable.
