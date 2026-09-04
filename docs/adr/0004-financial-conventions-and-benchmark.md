# ADR 0004 — Financial Conventions and Benchmark

- Status: Accepted
- Date: 2026-09-04

## Context

Portfolio valuation, analytics, optimization, simulation, and benchmark comparisons must use compatible assumptions. The phrase “S&P 500 benchmark” is ambiguous because a price index excludes dividends while an adjusted ETF series can approximate total return.

## Decision

Use one immutable, framework-independent `FinancialConventions` object as the source of calculation defaults:

- USD base currency;
- daily adjusted-close prices;
- daily simple returns;
- 252 trading periods per year;
- no missing-value imputation;
- timestamp-intersection alignment, with inadequate history and material gaps treated as explicit data errors.

Use adjusted `SPY` prices as the initial S&P 500 total-return ETF proxy. Label it as a proxy and keep its metadata separate from S&P 500 constituent membership.

## Consequences

Positive:

- calculations and comparisons share explicit assumptions;
- dividend-adjusted benchmark behavior is practical for the initial data provider;
- domain calculations remain independent of runtime configuration frameworks.

Negative:

- SPY has fees and tracking differences and is not the official index;
- timestamp intersection may reduce the usable history and therefore requires visible diagnostics.
