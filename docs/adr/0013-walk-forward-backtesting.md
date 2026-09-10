# ADR 0013 — Walk-forward backtesting

- Status: Accepted
- Date: 2026-09-10

## Decision

Add a framework-independent `BacktestEngine` consuming typed price/configuration values and
injected allocation strategies. Expected-return, covariance and optimizer contracts remain
unchanged. The CLI composes the historical and fixed-63-observation-half-life forecast estimators
with historical sample covariance and the existing deterministic SLSQP optimizer. Both receive
the same explicit risk aversion and cap; no evaluation-period tuning occurs.

For an execution at price index `t`, a rolling training window of `N` returns uses price indexes
`t-N-1` through `t-1`, inclusive. Its return timestamps run from `t-N` through `t-1`.
Expanding training retains the initial rolling window's starting price and extends through `t-1`.
No execution-day price enters estimation. At the execution close, target fractional holdings are
established; the first earned interval is `t` to `t+1`. On later execution dates, existing holdings
first earn the incoming return, then rebalance without costs. Weights drift between executions.

Execute every configured number of SPY observations (default 21), anchored to the first
evaluation session. Keep a scheduled allocation even when it falls on the final evaluation date,
so extending an evaluation preserves all earlier decision records; it earns no return until the
next session. Include partial final holding intervals. Require at least two evaluation returns.

Each selected window mode produces historical and forecast strategies. Add one equal-weight
strategy, reset on the same schedule, and one SPY buy-and-hold strategy. All series begin with
identical USD capital at the same close and share every evaluation date. The cap applies to
optimized target weights, not drifted weights or the SPY baseline. Existing historical analytics'
buy-and-hold equal-weight definition is unchanged and differs deliberately from this baseline.

## Data and reproducibility

Acquire through `MarketDataProvider` and freeze daily USD adjusted-close prices, selected current
constituent metadata, constituent as-of date, provider provenance and SHA-256 identity. Replay is
offline and validates the snapshot hash, schema, ordering, conventions and coverage. It never
refreshes prices or resolves current membership. Configuration and JSON schemas reject unknown
fields. No HTTP endpoint, web workflow, persistent jobs or database migration is introduced.

SPY observations define the session calendar. Every asset must cover every session, including
warm-up. Reject missing or extra asset dates instead of applying timestamp intersection. This
stricter backtest policy prevents silent calendar changes without modifying other application
alignment. A session missing from all series cannot be detected without an independent exchange
calendar; this limitation is disclosed.

The fixed demonstration basket is AAPL, MSFT, JPM, JNJ and XOM. The evaluation runs from the
first 2019 SPY session through the last 2025 session. The proposed 2018-01-01 snapshot start
does not supply 253 preceding prices: the frozen data has 251 observations in 2018. Extend only
the warm-up boundary to 2017-12-28, providing 253 prices before execution on 2019-01-02.
Do not shorten training or move the evaluation start silently. Other defaults are 252 training
returns, both window modes, 21-session cadence, USD 10,000, lambda 3.0 and 40% maximum weight.

Canonical JSON records configuration, model/solver settings, runtime versions, daily accounting,
training windows, estimated inputs, target weights and solver diagnostics. The report identity
includes source snapshot identity and excludes report-generation wall time. Frozen retrieval times
remain provenance. Exact replay is expected in the locked environment; numerical comparisons
across platforms allow solver tolerances. Matplotlib produces inline SVG plots in self-contained
HTML with no network assets. Both outputs are deterministic in the same environment.

## Metrics and failure policy

Total return is final/initial equity minus one; annualized realized return is that equity ratio
raised to `252 / number_of_evaluation_returns`, minus one. Volatility uses sample standard
deviation of daily portfolio returns times square root of 252. Drawdown is equity/prior-running-peak
minus one; maximum drawdown is reported as a positive loss magnitude. Initial equity is included
in the peak calculation. Estimated arithmetic annual means remain separately labelled.

Invalid data, infeasible constraints and failed optimization stop the entire comparison. Decision
failures include strategy and execution date; there is no fallback, skipped window or successful
partial report. Data and report rendering sit outside the domain.

## Limitations and validation

This is a comparison of hypothetical decisions on realized historical prices, not a claim of
forecast superiority. Current membership and a fixed chosen basket introduce survivorship and
selection bias. Adjusted prices are revised data, not historical point-in-time vintages. Execution
at adjusted closes is idealized, with fractional allocation and reinvested adjusted-price returns;
costs, slippage, taxes, turnover constraints, historical constituent reconstruction and parameter
search are outside Week 9. No current-portfolio comparison is added.

Tests cover hand-calculated accounting, exact window boundaries, execution lag, future-data
perturbations, prefix invariance, target constraints, data validation, contextual failures,
offline CLI replay and the frozen real-data comparison. See `docs/TESTING.md` for evidence and
`examples/backtest/week9/README.md` for reproduction commands.
