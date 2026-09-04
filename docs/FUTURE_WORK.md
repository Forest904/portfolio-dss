# Future Work

This file collects ideas that are intentionally outside the Phase B delivery target.

## Broader investment universes

The initial S&P 500 universe can be replaced or supplemented through the universe/provider contracts.

Candidates:

- Nasdaq-100;
- all Nasdaq-listed equities;
- broader US market;
- international equities;
- ETFs and multi-asset portfolios.

## Short selling

Phase C can allow negative weights with explicit limits such as:

- minimum weight per asset;
- gross exposure constraint;
- net exposure constraint;
- leverage limits.

This requires changes to optimization constraints, validation, explanations, and risk communication.

## Multi-source expected-return signals

Future return signals may include:

- social sentiment;
- news sentiment;
- company fundamentals;
- macroeconomic variables;
- analyst estimates;
- advanced time-series/ML forecasts.

These should implement `ExpectedReturnEstimator` and optionally be combined through `SignalAggregator`.

## Sentiment project integration

A separate sentiment-analysis project could expose outputs such as:

```text
SentimentReturnSignal
- asset_id
- horizon
- expected_return_adjustment or score
- confidence
- source coverage
- model version
- generated_at
```

The DSS should treat this as one uncertain signal among several, not as absolute truth.

## Advanced optimization

Potential methods:

- Black-Litterman;
- CVaR optimization;
- robust optimization;
- shrinkage covariance;
- transaction-cost-aware rebalancing;
- turnover constraints;
- cardinality constraints;
- multi-period portfolio optimization.

## Advanced forecasting

Only after the backtesting infrastructure is reliable:

- regularized regression;
- tree-based models;
- gradient boosting;
- temporal deep learning;
- probabilistic forecasting.

Every advanced model should be compared with simple baselines out of sample.
