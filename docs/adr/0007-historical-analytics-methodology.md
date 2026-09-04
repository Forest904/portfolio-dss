# ADR 0007 — Historical Analytics Methodology

- Status: Accepted
- Date: 2026-09-04

## Context

Historical portfolio, equal-weight, and S&P 500 comparisons need an explicit interpretation of
holdings and annualization. Otherwise, apparently comparable results can embed different
rebalancing or observation assumptions.

## Decision

- Interpret entered quantities as a buy-and-hold portfolio throughout the effective window.
- Construct the equal-weight alternative by investing equal dollars in the selected assets on the
  first common date, then allow its weights to drift without rebalancing.
- Align every selected asset and SPY on one timestamp intersection and require at least 253 common
  adjusted-close prices (252 simple daily returns).
- Report geometric CAGR, total return, and annualized sample volatility using 252 periods per year.
- Estimate asset risk with annualized sample covariance and Pearson sample correlation. Preserve
  the analysis when an asset has zero variance by returning undefined correlations as `null` with
  a diagnostic.
- Measure end-date concentration with largest and top-three weights, HHI, and effective count at
  both asset and current-sector levels.
- Assume no rebalancing, transaction costs, or taxes.

## Consequences

The current portfolio reflects weight drift and is understandable as a history of the quantities
the user entered. All three performance paths share identical observations. The equal-weight
result is an alternative initial allocation rather than a cost-free daily-rebalanced strategy.
Current constituent and sector metadata retain the survivorship-bias limitation documented for
the initial universe.
