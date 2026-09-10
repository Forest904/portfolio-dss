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

Week 11 stores price snapshots per asset. A fresh snapshot can serve asset-subset and contained-range
requests when it covers the entire requested interval. Partial intervals are never stitched across
retrieval times. Composed histories retain requested ordering, use the oldest contributing retrieval
time for freshness, and receive a new content hash. SQLite hash validation, WAL/busy-timeout handling,
atomic writes, and pruning make corrupt or concurrent cache access fail as an ordinary cache miss
rather than leaking invalid financial data. See ADR 0015.

## Reproducibility

### Walk-forward snapshots (Week 9)

Backtesting freezes normalized prices and current constituent metadata with provider provenance
and a snapshot SHA-256 hash; replay validates the snapshot and requires no provider calls.
Unlike analysis timestamp-intersection alignment, every basket asset must have every SPY session
in the configured history, including warm-up. Missing or extra asset sessions fail the comparison;
no values are filled and no dates are dropped. SPY is the calendar source, so a date missing from
all series cannot be detected without an independent exchange calendar.

The checked-in demonstration snapshot and report are under `examples/backtest/week9/`.
The warm-up begins 2017-12-28 to provide 253 prices before the first 2019 execution. Current
membership and revised adjusted prices are disclosed limitations, not point-in-time data claims.
See ADR 0013 and the example README for offline replay and acquisition commands.

### Analysis provenance

Every generated analysis should be traceable to:

- universe version/as-of date;
- data provider;
- data range;
- return convention;
- estimator configuration;
- risk model configuration;
- optimizer configuration;
- simulation seed when applicable.
