"use client";

import { useState } from "react";
import { ReturnComparison } from "../expected-returns/return-comparison";
import { SimulationResults } from "../portfolio-simulation/simulation-results";

import type { DecisionFact, FrontierReport, ProfileName } from "./types";

const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 });
const signed = new Intl.NumberFormat("en-US", { signDisplay: "exceptZero", maximumFractionDigits: 2 });
const labels: Record<string, string> = {
  conservative: "Conservative", moderate: "Moderate", aggressive: "Aggressive",
  current: "Current portfolio", equal_weight: "Equal weight", sp500_proxy: "S&P 500 (SPY ETF proxy)",
};
const colors: Record<string, string> = { current: "#426a8c", equal_weight: "#b06a26", sp500_proxy: "#7b528f" };

function factText(fact: DecisionFact): string {
  const comparison = labels[fact.comparison ?? ""] ?? fact.comparison;
  switch (fact.kind) {
    case "expected_return_change": return `Estimated annual return: ${signed.format(fact.value)} percentage points versus ${comparison}.`;
    case "volatility_change": return `Estimated annual volatility: ${signed.format(fact.value)} percentage points versus ${comparison}.`;
    case "allocation_change": return `${fact.subject} allocation: ${signed.format(fact.value)} percentage points versus current holdings.`;
    case "largest_holding": return `Largest holding: ${fact.subject}, ${percent.format(fact.value)} of the portfolio.`;
    case "concentration": return `Holding concentration (HHI): ${fact.value.toFixed(3)} on a 0–1 scale; higher values mean more concentrated weights.`;
    case "binding_cap": return `${fact.subject} reaches the configured weight cap at ${percent.format(fact.value)}.`;
  }
}

export function FrontierResults({ report, suggestedProfile, alternatives, capital, stale = false }: {
  report: FrontierReport;
  stale?: boolean;
  suggestedProfile?: ProfileName;
  capital?: string;
  alternatives?: { profile: ProfileName; allocations: { asset_id: string; weight: number; amount: string }[] }[];
}) {
  const [selected, setSelected] = useState<ProfileName>(suggestedProfile ?? "moderate");
  const dollars = alternatives?.find((item) => item.profile === selected)?.allocations;
  const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
  const profile = report.frontier.profiles.find((item) => item.name === selected)!;
  const point = report.frontier.points.find((item) => item.id === profile.point_id)!;
  const current = report.references.find((item) => item.id === "current");
  const values = [...report.frontier.points, ...report.references].map((item) => item.metrics);
  const width = 800, height = 380, left = 85, right = 30, top = 28, bottom = 72;
  const minX = Math.min(...values.map((item) => item.volatility));
  const maxX = Math.max(...values.map((item) => item.volatility));
  const minY = Math.min(...values.map((item) => item.expected_return));
  const maxY = Math.max(...values.map((item) => item.expected_return));
  const padX = Math.max((maxX - minX) * 0.1, 0.005);
  const padY = Math.max((maxY - minY) * 0.1, 0.005);
  const xLow = Math.max(0, minX - padX), xHigh = maxX + padX;
  const yLow = minY - padY, yHigh = maxY + padY;
  const x = (value: number) => left + (value - xLow) / (xHigh - xLow) * (width - left - right);
  const y = (value: number) => height - bottom - (value - yLow) / (yHigh - yLow) * (height - top - bottom);

  return <section className="analysis-results frontier-results" aria-labelledby="frontier-title">
    <div className="result-heading"><div><p className="eyebrow">Decision alternatives</p><h2 id="frontier-title">Explore the trade-off</h2></div>
      <p>{report.window.effective_start} – {report.window.effective_end}<br />{report.window.return_observations} shared daily returns</p></div>
    <p className="supporting-copy">These are model estimates, not guaranteed future outcomes. Profiles describe relative choices among {suggestedProfile ? "eligible S&P 500 stocks" : "your selected stocks"}.</p>
    {suggestedProfile && <p className="data-card">Questionnaire suggestion: <strong>{labels[suggestedProfile]}</strong>. {selected === suggestedProfile ? "Showing your suggested allocation." : `Exploring the ${labels[selected]} alternative; your questionnaire suggestion is unchanged.`}</p>}
    <fieldset className="profile-controls"><legend>Risk preference</legend>
      {report.frontier.profiles.map((item) => <label key={item.name} className={selected === item.name ? "profile-option selected" : "profile-option"}>
        <input type="radio" name="risk-profile" value={item.name} checked={selected === item.name} onChange={() => setSelected(item.name)} />
        <span><strong>{labels[item.name]}</strong><small>{percent.format(item.fraction)} of the achievable return range</small></span>
      </label>)}
    </fieldset>
    {new Set(report.frontier.profiles.map((item) => item.point_id)).size < 3 && <p className="data-card" role="status">Some profiles coincide: the available assets and constraints do not provide three distinct efficient allocations.</p>}
    <figure className="chart-card" aria-labelledby="frontier-chart-title">
      <figcaption><h3 id="frontier-chart-title">Estimated efficient frontier</h3><p className="fine-print">Selected: {labels[selected]}. Both axes show annualized estimates.</p></figcaption>
      <div className="frontier-chart-scroll"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Estimated annual risk and return frontier, ${labels[selected]} selected. Numeric values follow in tables.`}>
        {[0, 1, 2, 3, 4].map((index) => {
          const xv = xLow + index / 4 * (xHigh - xLow), yv = yLow + index / 4 * (yHigh - yLow);
          return <g key={index} className="frontier-tick">
            <line x1={left} x2={width - right} y1={y(yv)} y2={y(yv)} stroke="#dce4de" />
            <text x={left - 12} y={y(yv) + 4} textAnchor="end">{percent.format(yv)}</text>
            <text x={x(xv)} y={height - bottom + 24} textAnchor="middle">{percent.format(xv)}</text>
          </g>;
        })}
        <text x={(width + left - right) / 2} y={height - 15} textAnchor="middle">Estimated annual volatility (%)</text>
        <text transform={`translate(19 ${(height + top - bottom) / 2}) rotate(-90)`} textAnchor="middle">Estimated annual return (%)</text>
        <polyline points={report.frontier.points.map((item) => `${x(item.metrics.volatility)},${y(item.metrics.expected_return)}`).join(" ")} fill="none" stroke="#236449" strokeWidth="3" />
        {report.frontier.points.map((item) => <circle key={item.id} cx={x(item.metrics.volatility)} cy={y(item.metrics.expected_return)} r="2.5" fill="#236449" />)}
        {report.references.map((item, index) => <g key={item.id}>
          <rect x={x(item.metrics.volatility) - 6} y={y(item.metrics.expected_return) - 6} width="12" height="12" fill={colors[item.id]} stroke="white" strokeWidth="1.5" />
          <text x={x(item.metrics.volatility) + 9} y={y(item.metrics.expected_return) - 9} fontSize="12" fill={colors[item.id]}>{index + 1}</text>
          <title>{labels[item.id]}: return {percent.format(item.metrics.expected_return)}, volatility {percent.format(item.metrics.volatility)}</title>
        </g>)}
        {report.frontier.profiles.map((item) => {
          const p = report.frontier.points.find((candidate) => candidate.id === item.point_id)!;
          return <circle key={item.name} cx={x(p.metrics.volatility)} cy={y(p.metrics.expected_return)} r={selected === item.name ? 9 : 5} fill={selected === item.name ? "#123d2c" : "white"} stroke="#236449" strokeWidth="2"><title>{labels[item.name]}</title></circle>;
        })}
      </svg></div>
      <div className="chart-legend"><span><i style={{ background: "#236449" }} />Efficient frontier · circles: profiles</span>
        {report.references.map((item, index) => <span key={item.id}><i style={{ background: colors[item.id] }} />{index + 1}. {labels[item.id]}</span>)}
      </div>
    </figure>
    <div aria-live="polite" aria-atomic="true" className="metrics-grid" aria-label="Selected alternative metrics">
      <article className="metric"><span>Selected alternative</span><strong>{labels[selected]}</strong></article>
      <article className="metric"><span>Estimated annual arithmetic return</span><strong>{percent.format(point.metrics.expected_return)}</strong></article>
      <article className="metric"><span>Estimated annual volatility</span><strong>{percent.format(point.metrics.volatility)}</strong></article>
    </div>
    <section className="data-card"><h3>{current ? `Allocation: current vs ${labels[selected]}` : `Target allocation: ${labels[selected]}`}</h3>
      <p className="fine-print">{current ? "Target portfolio weights; changes are percentage points." : "Illustrative USD allocation of your capital, not share purchases. Cent rounding does not change target weights."}</p>
      <div className="table-scroll allocation-scroll"><table aria-label="Allocation comparison"><thead><tr><th>Asset</th>{current && <th>Current weight</th>}<th>{labels[selected]} weight</th>{current && <th>Change (pp)</th>}{dollars && <th>Amount (USD)</th>}</tr></thead><tbody>
        {point.weights.asset_ids.map((asset, index) => <tr key={asset}><th>{asset}</th>{current && <td>{percent.format(current.weights.weights[index])}</td>}<td>{percent.format(point.weights.weights[index])}</td>{current && <td>{signed.format(100 * (point.weights.weights[index] - current.weights.weights[index]))}</td>}{dollars && <td>{usd.format(Number(dollars[index].amount))}</td>}</tr>)}
      </tbody></table></div>
    </section>
    <section className="data-card"><h3>Comparable annual estimates</h3><div className="table-scroll"><table aria-label="Risk and return comparison"><thead><tr><th>Portfolio</th><th>Estimated return</th><th>Estimated volatility</th><th>Constraints</th></tr></thead><tbody>
      <tr><th>{labels[selected]}</th><td>{percent.format(point.metrics.expected_return)}</td><td>{percent.format(point.metrics.volatility)}</td><td>Valid</td></tr>
      {report.references.map((item) => <tr key={item.id}><th>{labels[item.id]}</th><td>{percent.format(item.metrics.expected_return)}</td><td>{percent.format(item.metrics.volatility)}</td><td>{item.constraint_status === "valid" ? "Valid" : item.constraint_status === "exceeds_max_weight" ? "Exceeds weight cap" : "Reference only; outside investable stocks"}</td></tr>)}
    </tbody></table></div></section>
    <section className="data-card"><h3>Decision facts · {labels[selected]}</h3><ul>{report.facts.filter((fact) => fact.profile === selected).map((fact) => <li key={fact.id}>{factText(fact)}</li>)}</ul></section>
    {report.expected_return_comparison && <ReturnComparison comparison={report.expected_return_comparison} />}
    <SimulationResults stale={stale} report={report} selected={selected} capital={capital ?? report.holdings_capital ?? null} />
    <section className="data-card"><h3>Assumptions</h3><ul>{report.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></section>
    <details className="details-card"><summary>Advanced frontier details</summary>
      <h3>Frontier values</h3><div className="table-scroll"><table><thead><tr><th>Point</th><th>Estimated annual return</th><th>Estimated annual volatility</th></tr></thead><tbody>{report.frontier.points.map((item) => <tr key={item.id}><th>{item.id}</th><td>{percent.format(item.metrics.expected_return)}</td><td>{percent.format(item.metrics.volatility)}</td></tr>)}</tbody></table></div>
      <h3>Model and configuration</h3><p>{report.expected_return_model.estimator_name} · {report.risk_model.estimator_name}</p>
      <p>Mapping: {report.profile_configuration.version} · {report.profile_configuration.fractions.map((value) => percent.format(value)).join(" / ")}. Maximum weight: {report.constraints.max_weight === null ? "No additional cap" : percent.format(report.constraints.max_weight)}.</p>
      <h3>Diagnostics and provenance</h3><ul>{report.diagnostics.map((item, index) => <li key={index}>{item}</li>)}</ul>
      <pre>{JSON.stringify({ models: { expected_return: report.expected_return_model, risk: report.risk_model, benchmark_expected_return: report.benchmark_expected_return_model, benchmark_risk: report.benchmark_risk_model }, conventions: report.conventions, window: report.window, solvers: report.frontier.points.map((item) => ({ point: item.id, ...item.solver })), universe: report.universe_provenance, prices: report.price_provenance }, null, 2)}</pre>
      <p className="fine-print">Report: {report.report_hash}</p>
    </details>
  </section>;
}
