# ADR 0006 — Market Data Sources and Local Cache

- Status: Accepted
- Date: 2026-09-04

## Context

Week 2 needs a replaceable market-data source, a current S&P 500 directory, and reproducible
valuation snapshots without coupling domain calculations to vendor libraries.

## Decision

- Use Yahoo Finance through `yfinance` for daily adjusted-close prices. The adapter explicitly
  disables automatic OHLC adjustment and selects `Adj Close`.
- Use Wikipedia's current S&P 500 table for ticker, company, sector, and sub-industry metadata.
- Keep canonical S&P tickers in the domain and translate vendor symbols only in the adapter
  (`BRK.B` becomes `BRK-B` for Yahoo).
- Cache normalized payloads and provenance in a local SQLite database under `data/`.
- Use current constituent membership for interactive and historical-date valuations. Historical
  membership is not reconstructed, so survivorship bias is disclosed in every relevant response.
- Permit a bounded stale-cache fallback when refresh fails; never silently serve data outside the
  configured seven-day limit for a current valuation.

## Consequences

Domain and application code remain independent from pandas, yfinance, HTTP, and SQLite. Repeated
requests can reproduce a snapshot by its source hashes, but clearing the local cache or upstream
corporate-action revisions can change later retrievals. Yahoo Finance data is intended for this
educational project and is not a production market-data service.
