# ADR 0002 — Expected Returns as Replaceable Signals

- Status: Accepted
- Date: 2026-09-04

## Context

The initial mathematical model needs a vector of expected returns. Historical averages are the simplest estimator, but the project should later support forecasting, sentiment, fundamentals, and other sources without rewriting portfolio optimization.

## Decision

Represent expected-return estimates through a stable `ExpectedReturnSignal` contract produced by `ExpectedReturnEstimator` implementations.

The optimizer consumes the signal output, not the estimator implementation.

Future multi-source combinations are handled by a separate `SignalAggregator`.

## Consequences

Positive:

- historical and forecast estimators are interchangeable;
- future sentiment integration does not affect optimizer code;
- backtesting can evaluate estimators through one common interface;
- model metadata and assumptions travel with the estimate.

Negative:

- horizon/annualization compatibility must be validated;
- signal combination introduces modeling choices that require careful explanation.
