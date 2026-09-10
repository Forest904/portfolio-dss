"use client";

import { useEffect, useRef, useState } from "react";
import { estimatorLabels } from "../expected-returns/estimator-selector";
import type { FrontierReport, ProfileName } from "../portfolio-frontier/types";
import { scenarioFromReport, type PortfolioSimulation, type Settings, type SimulationReport } from "./types";

const names: Record<string, string> = { conservative: "Conservative", moderate: "Moderate", aggressive: "Aggressive",
  current: "Current portfolio", equal_weight: "Equal weight", sp500_proxy: "S&P 500 (SPY ETF proxy)" };
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const pct = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

export function SimulationResults({ report, selected, capital, stale = false }: { stale?: boolean; report: FrontierReport; selected: ProfileName; capital: string | null }) {
  const [opened, setOpened] = useState(false);
  const [settings, setSettings] = useState<Settings>({ horizon_years: 1, paths: 10000, seed: 42 });
  const [comparator, setComparator] = useState(report.references.some((p) => p.id === "current") ? "current" : "equal_weight");
  const [result, setResult] = useState<SimulationReport | null>(null);
  const [resultKey, setResultKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const cache = useRef(new Map<string, SimulationReport>());
  const controller = useRef<AbortController | null>(null);
  const revision = useRef(0);
  const key = JSON.stringify([report.report_hash, capital, settings]);
  useEffect(() => () => { controller.current?.abort(); revision.current++; }, []);

  useEffect(() => { if (stale) { controller.current?.abort(); revision.current++; } }, [stale]);

  function changeSettings(next: Settings) {
    controller.current?.abort(); revision.current++;
    setLoading(false); setError(""); setSettings(next);
  }
  async function run() {
    if (stale) return;
    controller.current?.abort(); const version = ++revision.current;
    setError("");
    if (!capital) { setError("Refresh the recommendation to obtain its starting capital."); return; }
    if (![1, 3, 5].includes(settings.horizon_years) || ![1000, 10000, 50000].includes(settings.paths) || !Number.isInteger(settings.seed) || settings.seed < 0 || settings.seed > 4294967295) {
      setError("Choose a supported horizon and path count, and enter a whole-number seed from 0 to 4,294,967,295.");
      return;
    }
    const cached = cache.current.get(key);
    if (cached) { setResult(cached); setResultKey(key); setLoading(false); return; }
    const active = new AbortController(); controller.current = active; setLoading(true);
    try {
      const scenario = scenarioFromReport(report, capital, settings);
      const response = await fetch("/api/portfolio-simulations", { method: "POST", headers: { "Content-Type": "application/json" },
        signal: active.signal, body: JSON.stringify({ scenario }) });
      const payload = await response.json();
      if (version !== revision.current) return;
      if (!response.ok) throw new Error(payload.message ?? "Simulation failed. Please try again.");
      cache.current.set(key, payload);
      if (cache.current.size > 12) cache.current.delete(cache.current.keys().next().value!);
      setResult(payload); setResultKey(key);
    } catch (reason) {
      if (version === revision.current) setError(reason instanceof Error ? reason.message : "Simulation failed.");
    } finally { if (version === revision.current) setLoading(false); }
  }

  return <section className="data-card simulation-section" aria-labelledby="uncertainty-title">
    <h3 id="uncertainty-title">Explore possible outcomes</h3>
    <p>Return model: {report.expected_return_comparison ? estimatorLabels[report.expected_return_comparison.selected_estimator] : "Historical mean"}. Historical covariance estimates risk. The selected mean is held constant over the simulation horizon.</p>
    {stale && <p role="status">Simulation is stale because the estimator changed. Recalculate the recommendation first.</p>}
    <p>Simulated outcomes are not guaranteed. This model continuously maintains portfolio weights, including current holdings, with constant estimated return and volatility.</p>
    {!opened ? <div className="empty-state"><strong>Simulation not run</strong><p>Run it to compare ranges of possible outcomes; it will not replace the recommendation.</p><button disabled={stale} className="secondary-button" onClick={() => { setOpened(true); void run(); }}>Explore uncertainty</button></div> : <>
      <form className="simulation-controls" onSubmit={(event) => { event.preventDefault(); void run(); }}>
        <label>Simulation horizon<select value={settings.horizon_years} onChange={(e) => changeSettings({ ...settings, horizon_years: Number(e.target.value) })}>
          {[1, 3, 5].map((n) => <option key={n} value={n}>{n} {n === 1 ? "year" : "years"}</option>)}</select></label>
        <label>Compare with<select value={comparator} onChange={(e) => setComparator(e.target.value)}>
          {report.references.map((p) => <option key={p.id} value={p.id}>{names[p.id]}</option>)}</select></label>
        <details><summary>Advanced simulation controls</summary>
          <label>Simulated paths<select value={settings.paths} onChange={(e) => changeSettings({ ...settings, paths: Number(e.target.value) })}>
            {[1000, 10000, 50000].map((n) => <option key={n} value={n}>{n.toLocaleString("en-US")}</option>)}</select></label>
          <label>Random seed<input required type="number" min="0" max="4294967295" step="1" value={Number.isNaN(settings.seed) ? "" : settings.seed}
            onChange={(e) => changeSettings({ ...settings, seed: e.target.valueAsNumber })} /></label>
        </details>
        <button className="primary-button" disabled={loading || stale} type="submit">{loading ? "Simulating…" : "Run simulation"}</button>
      </form>
      {loading && <p role="status">Calculating possible outcomes…</p>}
      {error && <p role="alert">{error} Use Run simulation to retry.</p>}
      {result && <>
        {key !== resultKey && <p role="status">Results are stale: they use the previous settings. Run simulation to update.</p>}
        <SimulationCharts result={result} selected={selected} comparator={comparator} />
        <details><summary>Simulation assumptions and reproducibility</summary>
          <ul>{result.assumptions.statements.map((s) => <li key={s}>{s}</li>)}</ul>
          <pre>{JSON.stringify({ scenario: result.scenario, assumptions: result.assumptions, environment: result.numerical_environment,
            input_fingerprint: result.input_fingerprint, result_hash: result.result_hash }, null, 2)}</pre>
        </details>
      </>}
    </>}
  </section>;
}

function SimulationCharts({ result, selected, comparator }: { result: SimulationReport; selected: string; comparator: string }) {
  const pair = [result.portfolios.find((p) => p.id === selected)!, result.portfolios.find((p) => p.id === comparator)!];
  const years = result.scenario.configuration.horizon_years;
  const maximum = Math.max(...pair.flatMap((p) => p.fan.map((f) => f.percentiles[4]))) * 1.05;
  const medianDifference = pair[0].terminal_value.percentiles[2] - pair[1].terminal_value.percentiles[2];
  const downsideDifference = pair[0].terminal_value.percentiles[0] - pair[1].terminal_value.percentiles[0];
  const lossDifference = pair[0].probability_of_loss - pair[1].probability_of_loss;
  return <div className="simulation-output">
    <p>Starting capital: {usd.format(result.scenario.initial_capital)} USD for each portfolio. Horizon: {years} {years === 1 ? "year" : "years"}; {result.scenario.configuration.paths.toLocaleString("en-US")} paths; seed {result.scenario.configuration.seed}.</p>
    <p className="fine-print">Nominal USD, dividends reinvested, no cash flows, costs, taxes or inflation. The bands show pointwise simulated outcomes, not individual paths or uncertainty in estimated parameters.</p>
    <aside className="simulation-takeaway"><strong>What this comparison says:</strong> The selected portfolio&apos;s median terminal value is {usd.format(Math.abs(medianDifference))} {medianDifference >= 0 ? "higher" : "lower"}; its P5 downside outcome is {usd.format(Math.abs(downsideDifference))} {downsideDifference >= 0 ? "higher" : "lower"}; and its modeled loss probability is {pct.format(Math.abs(lossDifference))} {lossDifference >= 0 ? "higher" : "lower"} than {names[comparator]}. These are marginal simulated estimates, not odds of outperforming.</aside>
    <div className="simulation-fans">{pair.map((p, i) => <Fan key={p.id} portfolio={p} maximum={maximum} years={years} color={i === 0 ? "#236449" : "#426a8c"} />)}</div>
    <Histogram pair={pair} edges={result.histogram_edges} years={years} paths={result.scenario.configuration.paths} />
    <p>Loss means finishing below starting nominal capital at {years} {years === 1 ? "year" : "years"}, not a temporary drawdown. These are marginal distributions; no probability of one portfolio beating another is calculated.</p>
    <div className="table-scroll" role="region" aria-label="Scrollable terminal metrics" tabIndex={0}><table aria-label="Terminal simulation metrics"><caption>Simulated terminal outcomes at {years} {years === 1 ? "year" : "years"}</caption>
      <thead><tr><th>Metric</th>{pair.map((p) => <th key={p.id}>{names[p.id]}</th>)}</tr></thead>
      <tbody>
        {([['Mean', 'mean'], ['Standard deviation', 'standard_deviation']] as const).map(([label, field]) => <tr key={field}><th>{label} (USD / cumulative return)</th>{pair.map((p) => <td key={p.id}>{usd.format(p.terminal_value[field])} / {pct.format(p.terminal_return[field])}</td>)}</tr>)}
        {result.assumptions.percentile_levels.map((level, i) => <tr key={level}><th>{level === 50 ? "Median (P50)" : `P${level}`} (USD / cumulative return)</th>{pair.map((p) => <td key={p.id}>{usd.format(p.terminal_value.percentiles[i])} / {pct.format(p.terminal_return.percentiles[i])}</td>)}</tr>)}
        <tr><th>Probability of loss</th>{pair.map((p) => <td key={p.id}>{pct.format(p.probability_of_loss)}</td>)}</tr>
      </tbody></table></div>
  </div>;
}

function Fan({ portfolio, maximum, years, color }: { portfolio: PortfolioSimulation; maximum: number; years: number; color: string }) {
  const x = (month: number) => 75 + month / (years * 12) * 395;
  const y = (value: number) => 245 - value / maximum * 215;
  const line = (index: number) => portfolio.fan.map((p) => `${x(p.month)},${y(p.percentiles[index])}`).join(" ");
  const band = (lo: number, hi: number) => `${line(hi)} ${[...portfolio.fan].reverse().map((p) => `${x(p.month)},${y(p.percentiles[lo])}`).join(" ")}`;
  return <figure className="chart-card"><figcaption><strong>{names[portfolio.id]} — simulated value</strong></figcaption>
    <div className="simulation-chart-scroll" role="region" aria-label={`${names[portfolio.id]} fan chart, scroll horizontally`} tabIndex={0}>
    <svg viewBox="0 0 500 310" role="img" aria-label={`${names[portfolio.id]} ${years}-year percentile fan, USD`}>
      {[0, 1, 2, 3, 4].map((n) => <g key={n}><line x1="75" x2="470" y1={y(maximum * n / 4)} y2={y(maximum * n / 4)} stroke="#dce4de" /><text x="67" y={y(maximum * n / 4) + 4} textAnchor="end">{compact.format(maximum * n / 4)}</text></g>)}
      <polygon points={band(0, 4)} fill={color} opacity="0.15" /><polygon points={band(1, 3)} fill={color} opacity="0.28" />
      <polyline points={line(2)} fill="none" stroke={color} strokeWidth="3" />
      {[0, years / 2, years].map((n) => <text key={n} x={x(n * 12)} y="266" textAnchor="middle">{n}</text>)}
      <text x="265" y="295" textAnchor="middle">Elapsed years</text><text x="18" y="140" transform="rotate(-90 18 140)" textAnchor="middle">Value (USD)</text>
    </svg></div><p className="fine-print">Line: median · inner band: 25–75% · outer band: 5–95%</p>
  </figure>;
}

function Histogram({ pair, edges, years, paths }: { pair: PortfolioSimulation[]; edges: number[]; years: number; paths: number }) {
  const maximum = Math.max(1, ...pair.flatMap((p) => p.histogram_counts));
  const colors = ["#236449", "#426a8c"];
  return <figure className="chart-card"><figcaption><strong>Terminal value distribution at {years} {years === 1 ? "year" : "years"}</strong></figcaption>
    <p className="fine-print">Percentage of simulated paths in each USD value range.</p>
    <div className="simulation-chart-scroll simulation-histogram-scroll" role="region" aria-label="Terminal histogram, scroll horizontally" tabIndex={0}>
    <svg viewBox="0 0 800 310" role="img" aria-label="Terminal value histogram comparison, USD and percentage of simulated paths">
      {[0, 1, 2, 3, 4].map((n) => <g key={n}><line x1="80" x2="770" y1={245 - n / 4 * 215} y2={245 - n / 4 * 215} stroke="#dce4de" /><text x="70" y={249 - n / 4 * 215} textAnchor="end">{pct.format(maximum * n / 4 / paths)}</text></g>)}
      {pair.map((p, j) => p.histogram_counts.map((count, i) => <rect key={`${p.id}-${i}`} x={80 + i * 23 + j * 11} y={245 - count / maximum * 215} width="10" height={count / maximum * 215} fill={colors[j]}><title>{names[p.id]}: {usd.format(edges[i])}–{usd.format(edges[i + 1])} USD, {pct.format(count / paths)} of paths</title></rect>))}
      {[0, 10, 20, 30].map((n) => <text key={n} x={80 + n * 23} y="266" textAnchor="middle">{compact.format(edges[n])}</text>)}
      <text x="420" y="295" textAnchor="middle">Terminal value (USD)</text>
    </svg></div><div className="chart-legend">{pair.map((p, i) => <span key={p.id}><i style={{ background: colors[i] }} />{names[p.id]}</span>)}</div>
  </figure>;
}
