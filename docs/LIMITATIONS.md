# Limitations

Portfolio DSS is an educational decision-support system. It does not provide investment advice,
execute trades, guarantee outcomes, or perform a regulated suitability assessment.

## Data

- Production data depends on Yahoo Finance and Wikipedia availability and semantics. Adjusted-close
  history can be revised after retrieval.
- Current S&P 500 membership is applied to historical analysis, creating survivorship bias. The
  system does not reconstruct point-in-time constituents or classifications.
- SPY is an ETF total-return proxy, not the official S&P 500 index. All calculations use USD,
  daily adjusted close, simple returns, and 252-period annualization.
- Missing observations are never filled. Analysis uses timestamp intersection after rejecting
  material gaps; backtesting requires exact agreement with SPY sessions. Neither policy uses an
  independent exchange calendar.
- Cached values can be stale within the disclosed fallback bound. The cache is local and improves
  availability and reproducibility; it is not a source of business truth.

## Models and recommendations

- Historical returns and covariance estimates are sample estimates, not stable future parameters.
  The exponential forecast is a weighted historical mean, not a validated price-prediction model.
- Mean-variance results are sensitive to expected returns, covariance, the selected window, and
  constraints. Long-only stock portfolios cannot guarantee capital protection.
- Explanations are deterministic summaries of model facts. They contextualize a joint optimization
  result and do not prove that one asset or input caused an allocation in isolation.
- Costs, taxes, slippage, turnover constraints, integer shares, inflation, liabilities, and
  multi-currency effects are not modeled.

## Simulation and evaluation

- Monte Carlo uses constant parameters and continuously maintained weights under a lognormal
  approximation. Its bands omit parameter uncertainty and are not forecast confidence intervals.
- Backtests use revised adjusted-close data, idealized close execution, fractional holdings, and a
  selected basket. Selection and survivorship bias remain; historical performance does not establish
  forecast superiority or future performance.
- Week 11 case studies reuse five selected stocks and SPY from the frozen backtest snapshot. They
  exercise DSS journeys reproducibly but do not represent the full S&P 500.

## Operations

- The local SQLite cache and guided-job worker target a single API process. Horizontal scaling,
  distributed job ownership, user accounts, durable cloud storage, and service-level guarantees are
  outside Phase B.
- Performance results are measurements from named machines and locked dependency versions, not
  portable acceptance thresholds.
