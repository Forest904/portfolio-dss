# Week 9 frozen-data demonstration

Open [the standalone report](report/report.html) to compare all six strategies.
[Full-precision JSON](report/report.json), [configuration](config.json) and the
[frozen snapshot](snapshot.json) accompany it. No API or frontend server is required.

## Replay offline

From the repository root:

```powershell
cd apps/api
uv sync --locked
uv run python -m app.cli.backtest run --config ../../examples/backtest/week9/config.json --snapshot ../../examples/backtest/week9/snapshot.json --output ../../output/week9
```

After dependencies are installed, the run command requires no network. Open
`output/week9/report.html`; `report.json` contains full-precision daily equity, returns, closing
weights, training windows, estimated inputs, solver diagnostics, source provenance and hashes.
The published report lives separately so rerunning does not overwrite the reference artifact.

## Acquire another snapshot

This command accesses current constituent metadata and historical adjusted prices through the
existing Wikipedia/Yahoo adapters. Use a new destination to preserve the published snapshot:

```powershell
uv run python -m app.cli.backtest snapshot --config ../../examples/backtest/week9/config.json --snapshot ../../output/week9/new-snapshot.json
```

Explicit historical requests reuse the provider cache if present. A new download can differ
because adjusted prices are revised; reproducibility depends on retaining a frozen snapshot,
not redownloading it. Provider retrieval timestamps and hashes are embedded. The snapshot is
normalized data from Yahoo Finance and current constituent metadata from Wikipedia, not synthetic
or point-in-time historical membership data; source usage terms continue to apply.

## Configuration

Copy `config.json` to specify another fixed basket or period. All fields are explicit there;
unknown fields and invalid values fail. `window_modes` accepts `rolling`, `expanding`, or both.
`training_returns` is at least two; `rebalance_sessions` is at least one; `max_weight` accepts
a feasible fraction in `(0, 1]` or `null`. Risk aversion is finite and nonnegative; capital is
positive. The ordered snapshot basket must match the configuration exactly. A wider snapshot
can be replayed over narrower configured history bounds. Evaluation dates select SPY sessions
inclusively, and the report states the actual first and last sessions.

The demo evaluates 2019-01-02 through 2025-12-31 using AAPL, MSFT, JPM, JNJ and XOM. It uses
USD 10,000, risk aversion 3.0, a 40% optimized target cap and 21-session rebalancing. These are
fixed demonstration settings, not optimized against these results. Both estimator strategies
use the same covariance model and constraints. Equal weight resets on the same schedule; SPY
is held throughout and labelled as an S&P 500 ETF total-return proxy.

The snapshot starts **2017-12-28**, extending the proposed 2018-01-01 warm-up start by two
sessions: 2018 contains 251 SPY observations, but 252 training returns require 253 prices before
the first execution. Evaluation dates and the training length are unchanged. New configurations
with insufficient warm-up fail visibly instead of silently changing the requested experiment.

See [ADR 0013](../../../docs/adr/0013-walk-forward-backtesting.md) for timing, metrics, failure
policy and limitations. The report demonstrates historical evaluation; it is not evidence of a
guaranteed return or general forecast superiority.
