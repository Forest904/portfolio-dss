# ADR 0003 — Long-Only Optimization for Phase B

- Status: Accepted
- Date: 2026-09-04

## Context

Short selling increases modeling, UX, leverage, and explanation complexity. The main academic goal is a clear Decision Support System based on portfolio optimization under risk and uncertainty.

## Decision

Phase A/B portfolios use:

- `sum(x) = 1`;
- `x_i >= 0`;
- optional maximum weight per asset.

The optimization API models constraints explicitly so Phase C can add short-selling constraints without redesigning the optimizer boundary.

## Consequences

Positive:

- easier explanation for non-expert users;
- simpler optimization and validation;
- realistic for many retail-investor scenarios.

Negative:

- the feasible set excludes some mathematically efficient leveraged/short portfolios;
- short-selling research is deferred to Phase C.
