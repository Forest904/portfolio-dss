# Product Definition

## Vision

Build an interactive Decision Support System that helps a non-expert investor reason about portfolio choices under risk and uncertainty.

The system should not simply output an “optimal portfolio”. It should help the user understand:

- what they currently own;
- where the portfolio risk comes from;
- whether diversification is effective;
- what alternative allocations exist;
- how recommendations change when preferences change;
- how uncertain future outcomes are;
- how sensitive the decision is to the method used to estimate expected returns.

## Target user

The initial user is a retail investor with limited quantitative-finance knowledge who can identify stocks by ticker and understands basic ideas such as profit, loss, and risk.

The interface should use plain language first and expose mathematical details progressively.

## Initial investment universe

Phase A and B use the S&P 500 constituent universe plus the S&P 500 index as a benchmark.

The universe must be represented behind an interface so future versions can add:

- Nasdaq universes;
- broader US equities;
- international equities;
- ETFs or other asset classes.

## Main user journeys

### 1. Guided portfolio construction

1. User answers a small set of risk/preference questions.
2. User enters investable capital.
3. The DSS proposes one or more portfolios.
4. The user compares alternatives along the efficient frontier.
5. The system explains the recommendation.

### 2. Existing portfolio analysis

1. User enters ticker + quantity for each position.
2. The system values the current portfolio using a clearly stated valuation timestamp.
3. The system analyzes return, volatility, correlation, concentration, diversification, and benchmark-relative performance.
4. The DSS proposes changes according to the user's preferences.
5. The user compares current and recommended portfolios.

### 3. Uncertainty exploration

1. User selects a portfolio and horizon.
2. The system runs a Monte Carlo simulation using explicit assumptions.
3. The UI shows a distribution of outcomes rather than a single predicted price.
4. The user can compare the distribution of current and recommended portfolios.

### 4. Expected-return model comparison

The user can compare decisions produced with:

- historical expected returns;
- a simple explainable forecasting model.

The purpose is to study how expected-return estimation affects the portfolio decision.

## Product principles

- Explain before optimizing complexity.
- Show uncertainty instead of hiding it.
- Compare alternatives instead of declaring a single universal optimum.
- Keep assumptions visible.
- Prefer reproducible analysis over impressive but fragile models.
- Optimize for educational clarity without turning the application into a tutorial-only product.
