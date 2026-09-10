"use client";

import { useState } from "react";
import { estimatorLabels } from "./estimator-selector";
import type { ExpectedReturnComparison } from "./types";

const percent = (value: number) => `${(value * 100).toFixed(2)}%/year`;
const delta = (value: number) => `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)} pp/year`;
const labels: Record<string, string> = { current: "Current portfolio", recommended: "Recommended portfolio", equal_weight: "Equal weight", sp500_proxy: "S&P 500 (SPY)", conservative: "Conservative", moderate: "Moderate", aggressive: "Aggressive" };

export function ReturnComparison({ comparison }: { comparison: ExpectedReturnComparison }) {
  const [page, setPage] = useState(0);
  const pairs = [comparison.assets, ...(comparison.benchmark ? [comparison.benchmark] : [])];
  const assets = pairs.flatMap((pair) => pair.historical.signal.asset_ids.map((asset, i) => ({ asset, historical: pair.historical.signal.expected_returns[i], forecast: pair.forecast.signal.expected_returns[i] })));
  const pages = Math.ceil(assets.length / 25);
  const metadata = comparison.assets.forecast.metadata;
  return <section className="data-card expected-return-comparison" aria-label="Expected-return comparison">
    <h3>Historical vs forecast expected returns</h3>
    <p>Allocation calculated with: <strong>{estimatorLabels[comparison.selected_estimator]}</strong>.</p>
    <p>Both columns evaluate the same portfolio weights. Differences reflect the return model, not a second optimized allocation. Values are annualized arithmetic estimates, not observed CAGR or guaranteed outcomes.</p>
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Portfolio expected returns"><table>
      <thead><tr><th>Portfolio (same weights)</th><th>Historical (%/year)</th><th>Forecast (%/year)</th><th>Difference (percentage points/year)</th></tr></thead>
      <tbody>{comparison.portfolios.map((row) => <tr key={row.id}><th>{labels[row.id] ?? row.id}</th><td>{percent(row.historical_expected_return)}</td><td>{percent(row.forecast_expected_return)}</td><td>{delta(row.difference)}</td></tr>)}</tbody>
    </table></div>
    <details><summary>Asset estimates and estimator diagnostics</summary>
      <p>Training window: {metadata.estimation_start} to {metadata.estimation_end}; {metadata.observations} daily return observations. Forecast half-life: {metadata.half_life_observations} trading observations. Effective sample size: {metadata.effective_sample_size.toFixed(1)} weighted observations; latest observation weight: {(metadata.latest_observation_weight * 100).toFixed(2)}%.</p>
      <p>Weights are normalized over the complete aligned sample. The forecast assumes a constant future daily mean. Predictive accuracy will be evaluated out of sample; no accuracy claim is made here.</p>
      <ul>{pairs.flatMap((pair) => [pair.historical, pair.forecast]).flatMap((model) => model.signal.diagnostics).filter((v, i, all) => all.indexOf(v) === i).map((message) => <li key={message}>{message}</li>)}</ul>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Asset expected returns"><table>
        <thead><tr><th>Asset</th><th>Historical (%/year)</th><th>Forecast (%/year)</th><th>Difference (percentage points/year)</th></tr></thead>
        <tbody>{assets.slice(page * 25, (page + 1) * 25).map((row) => <tr key={row.asset}><th>{row.asset}</th><td>{percent(row.historical)}</td><td>{percent(row.forecast)}</td><td>{delta(row.forecast - row.historical)}</td></tr>)}</tbody>
      </table></div>
      {pages > 1 && <nav className="result-views" aria-label="Asset comparison pages"><button type="button" className="secondary-button" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous assets</button><span aria-live="polite">Page {page + 1} of {pages}</span><button type="button" className="secondary-button" disabled={page + 1 === pages} onClick={() => setPage(page + 1)}>Next assets</button></nav>}
      <p className="fine-print">Historical version: {comparison.assets.historical.metadata.version}. Forecast version: {metadata.version}. Weighting: {metadata.weighting_method}.</p>
    </details>
  </section>;
}
