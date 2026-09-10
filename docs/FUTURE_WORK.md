# Future Work

These extensions are outside the Phase B submission. Their priority follows the limitations exposed
by the current decision-support workflow rather than adding complexity for its own sake.

## 1. More realistic portfolio decisions

The current optimizer excludes costs, taxes, slippage, turnover, and integer-share execution. A
first Phase C increment should add transaction-cost and turnover constraints, followed by a separate
integer-share allocation step. Explanations must distinguish mathematical target weights from
executable trades.

Related limitation: [Models and recommendations](LIMITATIONS.md#models-and-recommendations).

## 2. Point-in-time data and broader evaluation

Historical analysis currently applies today’s S&P 500 membership to earlier periods. Point-in-time
constituents, delisted securities, and an independent exchange calendar would reduce survivorship
and calendar bias. Evaluation should then expand beyond the selected five-stock basket and include
multiple periods and market regimes.

Related limitations: [Data](LIMITATIONS.md#data) and
[Simulation and evaluation](LIMITATIONS.md#simulation-and-evaluation).

## 3. Stronger risk and uncertainty models

Potential replacements behind the existing contracts include shrinkage covariance, robust
optimization, CVaR, Black-Litterman, and parameter-uncertainty simulations. Each addition should be
compared with the simple baseline and disclose any new assumptions.

Related limitations: [Models and recommendations](LIMITATIONS.md#models-and-recommendations) and
[Simulation and evaluation](LIMITATIONS.md#simulation-and-evaluation).

## 4. Multiple expected-return signals

Future estimators may use fundamentals, macroeconomic variables, analyst estimates, news, or social
sentiment. They should implement `ExpectedReturnEstimator` and emit compatible, versioned signals. A
future `SignalAggregator` may combine them with explicit weights, coverage checks, and diagnostics.
Advanced machine-learning models should enter only after reliable out-of-sample comparisons against
the historical and exponential baselines.

## 5. Broader investment universes

The provider contracts can support the Nasdaq-100, broader US equities, international markets, ETFs,
or multi-asset portfolios. Multi-currency accounting and market-specific calendars must accompany
international expansion; they cannot be hidden inside the current USD convention.

Related limitation: [Data](LIMITATIONS.md#data).

## 6. Durable multi-user operation

The local SQLite cache and guided-job worker target one API process. A hosted version would require
durable shared storage, distributed job ownership, authentication, saved portfolios, rate limits,
monitoring, and explicit service objectives before horizontal scaling.

Related limitation: [Operations](LIMITATIONS.md#operations).

## Deferred product boundaries

Short selling, leverage, options, automated brokerage execution, high-frequency trading, and a full
robo-advisory suitability process remain outside the current product boundary. Any future inclusion
would require new constraints, validation, explanations, and regulatory review rather than a simple
UI switch.
