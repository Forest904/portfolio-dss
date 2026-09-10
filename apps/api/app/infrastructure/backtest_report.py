"""Standalone HTML rendering; calculations remain in the domain engine."""

from __future__ import annotations

import io
import json
from html import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from app.application.backtest import ASSUMPTIONS, canonical_json
from app.domain.backtest import BacktestReport

LABELS = {
    "historical_mean_rolling": "Historical · rolling",
    "simple_forecast_rolling": "Forecast · rolling",
    "historical_mean_expanding": "Historical · expanding",
    "simple_forecast_expanding": "Forecast · expanding",
    "equal_weight": "Equal weight · rebalanced",
    "sp500_proxy": "S&P 500 ETF total-return proxy (SPY)",
}
COLORS = ("#1769aa", "#c65312", "#17806d", "#8a479b", "#72700b", "#313b49")


def _chart(report: BacktestReport, *, drawdown: bool) -> str:
    with plt.rc_context({"svg.hashsalt": "portfolio-dss-week9", "font.size": 10}):
        figure, axis = plt.subplots(figsize=(11, 4.8), layout="constrained")
        for i, strategy in enumerate(report.strategies):
            axis.plot(
                mdates.date2num([p.observed_on for p in strategy.daily]),  # type: ignore[no-untyped-call]
                [p.drawdown * 100 if drawdown else p.equity_usd for p in strategy.daily],
                label=LABELS.get(strategy.id, strategy.id),
                color=COLORS[i % len(COLORS)],
                linestyle="--" if strategy.window_mode == "expanding" else "-",
                linewidth=1.5,
            )
        axis.set_ylabel("Drawdown from prior peak (%)" if drawdown else "Portfolio value (USD)")
        axis.set_xlabel("Historical evaluation date")
        locator = mdates.AutoDateLocator(minticks=4, maxticks=9)  # type: ignore[no-untyped-call]
        axis.xaxis.set_major_locator(locator)
        axis.xaxis.set_major_formatter(
            mdates.ConciseDateFormatter(locator)  # type: ignore[no-untyped-call]
        )
        axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
        axis.grid(alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
        axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=2, frameon=False)
        output = io.StringIO()
        figure.savefig(output, format="svg", metadata={"Date": None})
        plt.close(figure)
    svg = output.getvalue()
    svg = svg[svg.index("<svg") :]
    title = "Historical drawdown comparison" if drawdown else "Historical equity comparison in USD"
    return svg.replace("<svg ", f'<svg role="img" aria-label="{title}" ', 1)


def render_html(report: BacktestReport, report_hash: str, snapshot_hash: str) -> str:
    rows = []
    records = []
    for strategy in report.strategies:
        p = strategy.performance
        label = escape(LABELS.get(strategy.id, strategy.id))
        rows.append(
            f"<tr><th scope='row'>{label}</th><td>{p.total_return:.2%}</td>"
            f"<td>{p.annualized_return:.2%}</td><td>{p.annualized_volatility:.2%}</td>"
            f"<td>{p.maximum_drawdown:.2%}</td><td>${p.terminal_value_usd:,.2f}</td></tr>"
        )
        entries = []
        for d in strategy.decisions:
            training = (
                f"Training returns: {d.training.return_start} to {d.training.return_end} "
                f"({d.training.observations} observations)."
                if d.training
                else "Baseline allocation; no estimated model inputs."
            )
            allocations = []
            for index, (asset, weight) in enumerate(
                zip(
                    d.target_weights.asset_ids,
                    d.target_weights.weights,
                    strict=True,
                )
            ):
                estimate = (
                    f"{d.expected_returns.expected_returns[index]:.2%}"
                    if d.expected_returns
                    else "—"
                )
                allocations.append(
                    f"<tr><th scope='row'>{escape(asset)}</th><td>{weight:.2%}</td>"
                    f"<td>{estimate}</td></tr>"
                )
            numerical_record = escape(json.dumps(json.loads(canonical_json(d)), indent=2))
            entries.append(
                f"<details><summary>Execution {d.executed_on}</summary><p>{training}</p>"
                "<p>Estimated returns are model inputs, not realized performance.</p>"
                "<div class='scroll' tabindex='0' aria-label='Target allocation table'>"
                "<table><thead><tr><th>Asset</th><th>Target weight<br>% of capital</th>"
                "<th>Estimated return<br>% / year</th></tr></thead>"
                f"<tbody>{''.join(allocations)}</tbody></table></div>"
                "<details><summary>Full numerical record</summary>"
                "<p>Weights are fractions; estimated means and covariance use annual units.</p>"
                f"<pre>{numerical_record}</pre></details></details>"
            )
        count_label = "allocation" if len(entries) == 1 else "allocations"
        records.append(
            f"<details><summary>{label} · {len(entries)} {count_label}</summary>"
            f"<p>Model identity: {escape(strategy.identity)}</p>{''.join(entries)}</details>"
        )
    config = report.config
    series = report.strategies[0].daily
    assumptions = "".join(f"<li>{escape(a)}</li>" for a in ASSUMPTIONS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Portfolio DSS · Walk-forward backtest</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f5f7;color:#182a3b;
font:16px/1.6 system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:32px 24px}}
h1{{font-size:2.1rem;line-height:1.2}}h2{{font-size:1.35rem}}.eyebrow{{color:#1769aa;
font-weight:700;letter-spacing:.08em}}section{{background:white;border:1px solid #dbe2e9;
border-radius:12px;padding:24px;margin:24px 0}}.muted{{color:#516170}}.scroll{{overflow-x:auto}}
svg{{width:100%;min-width:650px;height:auto;display:block}}table{{border-collapse:collapse;
width:100%;font-size:.9rem}}th,td{{padding:12px;text-align:right;border-bottom:1px solid #dde4ea;
white-space:nowrap}}th:first-child{{text-align:left}}thead{{background:#eef3f7}}
summary{{cursor:pointer;font-weight:600;padding:12px 0}}details{{border-top:1px solid #dde4ea}}
details details{{margin:0 12px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;
background:#f3f5f7;padding:16px;font-size:12px}}code{{overflow-wrap:anywhere;font-size:12px}}
li{{margin:8px 0}}@media(max-width:600px){{main{{padding:20px 12px}}section{{padding:16px}}
h1{{font-size:1.7rem}}}}@media print{{body{{background:white}}section{{break-inside:avoid}}}}
</style></head><body><main>
<p class="eyebrow">PORTFOLIO DSS / WEEK 9</p><h1>Walk-forward strategy comparison</h1>
<p class="muted">Realized historical backtest outcomes under hypothetical allocations</p>
<p><strong>{series[0].observed_on} — {series[-1].observed_on}</strong> ·
{len(series) - 1:,} evaluation returns · Initial capital USD {config.initial_capital:,.2f}</p>
<section><h2>Shared decision settings</h2><p>Basket: {escape(", ".join(config.tickers))}.
Training: {config.training_returns} initial returns;
windows: {escape(", ".join(config.window_modes))}.
Rebalance every {config.rebalance_sessions} SPY sessions. Risk aversion: {config.risk_aversion:g}.
Optimized weight cap: {"none" if config.max_weight is None else f"{config.max_weight:.0%}"}.</p>
<p>Each decision uses data through the prior session and executes at the next close.
Holdings drift between rebalances. All strategies share the same evaluation period.</p></section>
<section><h2>Historical performance</h2><div class="scroll" tabindex="0"
aria-label="Historical performance table, scroll horizontally on small screens"><table>
<thead><tr><th>Strategy</th><th>Total return<br>evaluation period</th>
<th>Geometric return<br>% / year</th>
<th>Volatility<br>% / year</th><th>Maximum drawdown<br>evaluation period</th><th>Terminal USD</th>
</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p class="muted">252 sessions/year; sample standard deviation of daily portfolio returns.
Maximum drawdown is shown as a positive loss magnitude. This comparison does not establish
forecast superiority or guarantee future results.</p></section>
<section><h2>Portfolio value</h2><div class="scroll" tabindex="0"
aria-label="Equity chart, scroll horizontally on small screens">
{_chart(report, drawdown=False)}</div></section>
<section><h2>Drawdown from prior peak</h2><div class="scroll" tabindex="0"
aria-label="Drawdown chart, scroll horizontally on small screens">
{_chart(report, drawdown=True)}</div></section>
<section><h2>Assumptions and limitations</h2><ul>{assumptions}</ul></section>
<section><h2>Decision audit trail</h2><p>Expand a strategy and execution date to inspect its
training window, estimated inputs, weights, and solver diagnostics.</p>{"".join(records)}</section>
<section><h2>Reproducibility</h2><p>Report SHA-256: <code>{escape(report_hash)}</code></p>
<p>Snapshot SHA-256: <code>{escape(snapshot_hash)}</code></p>
<p>The adjacent JSON contains full-precision results, provenance, configuration, and runtime
versions. Offline replay uses the frozen snapshot; no live prices are requested.</p></section>
</main></body></html>"""
