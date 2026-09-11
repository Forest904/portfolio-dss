"use client";

import { useRef, useState } from "react";
import { SectionHeading } from "@/components/presentation";
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
    case "allocation_change": return `${fact.subject} allocation: ${signed.format(fact.value)} percentage points versus ${comparison}.`;
    case "largest_holding": return `Largest holding: ${fact.subject}, ${percent.format(fact.value)} of the portfolio.`;
    case "concentration": return `Holding concentration (HHI): ${fact.value.toFixed(3)} on a 0–1 scale; higher values mean more concentrated weights.`;
    case "concentration_change": return `Concentration change: ${signed.format(fact.value)} HHI versus ${comparison}.`;
    case "binding_cap": return `${fact.subject} reaches the configured weight cap at ${percent.format(fact.value)}.`;
    case "asset_expected_return": return `${fact.subject} estimated annual return: ${percent.format(fact.value)}.`;
    case "risk_contribution": return `${fact.subject} share of modeled portfolio risk: ${percent.format(fact.value)} (${comparison}).`;
    case "risk_contribution_change": return `${fact.subject} modeled risk-share change: ${signed.format(fact.value)} percentage points versus ${comparison}.`;
    case "equivalent_profile": return `${labels[fact.subject]} has the same allocation as ${labels[fact.comparison ?? ""]}.`;
  }
}

export function FrontierResults({ report, suggestedProfile, alternatives, capital, preferenceExplanation, stale = false }: {
  report: FrontierReport;
  stale?: boolean;
  suggestedProfile?: ProfileName;
  capital?: string;
  alternatives?: { profile: ProfileName; allocations: { asset_id: string; weight: number; amount: string }[] }[];
  preferenceExplanation?: string;
}) {
  const [selected, setSelected] = useState<ProfileName>(suggestedProfile ?? "moderate");
  const advanced = useRef<HTMLDetailsElement>(null);
  const dollars = alternatives?.find((item) => item.profile === selected)?.allocations;
  const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
  const profile = report.frontier.profiles.find((item) => item.name === selected)!;
  const point = report.frontier.points.find((item) => item.id === profile.point_id)!;
  const current = report.references.find((item) => item.id === "current");
  const baselineId = current ? "current" : "equal_weight";
  const baseline = report.references.find((item) => item.id === baselineId)!;
  const explanation = report.explanations?.find((item) => item.profile === selected);
  const selectedFacts = report.facts.filter((fact) => fact.profile === selected);
  const fallbackFacts = selectedFacts.filter((fact) =>
    fact.comparison === baselineId || fact.kind === "largest_holding" || fact.kind === "binding_cap"
  ).slice(0, 5);
  const allocationRows = point.weights.asset_ids.map((asset, index) => ({
    asset, index, target: point.weights.weights[index], previous: baseline.weights.weights[index] ?? 0,
    change: point.weights.weights[index] - (baseline.weights.weights[index] ?? 0),
  }));
  const focusedRows = [...allocationRows].sort((a, b) => current
    ? Math.abs(b.change) - Math.abs(a.change) || a.asset.localeCompare(b.asset)
    : b.target - a.target || a.asset.localeCompare(b.asset)).slice(0, 8);
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
    <SectionHeading eyebrow="Decision alternatives" title="Explore the trade-off" id="frontier-title">
      <p>{report.window.effective_start} – {report.window.effective_end}<br />{report.window.return_observations} shared daily returns</p>
    </SectionHeading>
    <p className="supporting-copy">These are model estimates, not guaranteed future outcomes. Profiles describe relative choices among {suggestedProfile ? "eligible S&P 500 stocks" : "your selected stocks"}.</p>
    <section className="decision-summary" aria-labelledby="decision-summary-title">
      <p className="eyebrow">Decision support</p><h3 id="decision-summary-title">Why this portfolio?</h3>
      {suggestedProfile && preferenceExplanation && <p className="preference-rationale"><strong>Why this profile:</strong> {preferenceExplanation}</p>}
      <p className="decision-lead">{explanation?.summary ?? `Compared with ${labels[baselineId]}, this alternative makes an explicit estimated return and volatility trade-off.`}</p>
      <div className="reason-grid">{explanation ? explanation.reasons.map((reason) => <article key={reason.id} className="reason-card">
        <span>{reason.category.replace("_", " ")}</span><h4>{reason.headline}</h4><p>{reason.detail}</p>
        {reason.evidence_fact_ids.length > 0 && <p className="evidence-links">Evidence: {reason.evidence_fact_ids.map((id, index) => <span key={id}>{index > 0 && " · "}<a href={`#fact-${id}`} onClick={() => { if (advanced.current) advanced.current.open = true; }}>{id}</a></span>)}</p>}
      </article>) : fallbackFacts.map((fact) => <article key={fact.id} className="reason-card"><span>decision fact</span><p>{factText(fact)}</p></article>)}</div>
      <p className="fine-print">Rule set: {explanation?.rule_version ?? "legacy fact display"}. Reasons are deterministic summaries of model facts, not financial advice.</p>
    </section>
    {suggestedProfile && <p className="profile-suggestion">Questionnaire suggestion: <strong>{labels[suggestedProfile]}</strong>. {selected === suggestedProfile ? "Showing your suggested allocation." : `Exploring the ${labels[selected]} alternative; your questionnaire suggestion is unchanged.`}</p>}
    <fieldset className="profile-controls"><legend>Risk preference</legend>
      {report.frontier.profiles.map((item) => <label key={item.name} className={selected === item.name ? "profile-option selected" : "profile-option"}>
        <input type="radio" name="risk-profile" value={item.name} checked={selected === item.name} onChange={() => setSelected(item.name)} />
        <span><strong>{labels[item.name]}</strong><small>{percent.format(item.fraction)} of the achievable return range</small></span>
      </label>)}
    </fieldset>
    {new Set(report.frontier.profiles.map((item) => item.point_id)).size < 3 && <p className="inline-notice" role="status">Some profiles coincide: the available assets and constraints do not provide three distinct efficient allocations.</p>}
    <div aria-live="polite" aria-atomic="true" className="metrics-grid" aria-label="Selected alternative metrics">
      <article className="metric"><span>Selected alternative</span><strong>{labels[selected]}</strong></article>
      <article className="metric"><span>Estimated annual arithmetic return</span><strong>{percent.format(point.metrics.expected_return)}</strong></article>
      <article className="metric"><span>Estimated annual volatility</span><strong>{percent.format(point.metrics.volatility)}</strong></article>
    </div>
    <section className="data-card"><h3>{current ? `Largest allocation changes · ${labels[selected]}` : `Largest target holdings · ${labels[selected]}`}</h3>
      <p className="fine-print">{current ? "The eight largest absolute changes are shown first. Changes are percentage points." : "The eight largest target holdings are shown. Amounts are illustrative, not share purchases."} The complete allocation is in advanced details.</p>
      <div className="table-scroll allocation-scroll"><table aria-label="Allocation comparison"><thead><tr><th>Asset</th>{current && <th>Current weight</th>}<th>{labels[selected]} weight</th>{current && <th>Change (pp)</th>}{dollars && <th>Amount (USD)</th>}</tr></thead><tbody>
        {focusedRows.map(({ asset, index }) => <tr key={asset}><th>{asset}</th>{current && <td>{percent.format(current.weights.weights[index])}</td>}<td>{percent.format(point.weights.weights[index])}</td>{current && <td>{signed.format(100 * (point.weights.weights[index] - current.weights.weights[index]))}</td>}{dollars && <td>{usd.format(Number(dollars[index].amount))}</td>}</tr>)}
      </tbody></table></div>
    </section>
    <aside className="assumption-strip" aria-label="Key recommendation assumptions">
      <strong>Read this as an estimate:</strong> {report.expected_return_model.estimator_name}; {report.window.return_observations} daily returns; stocks only; {report.constraints.max_weight === null ? "no additional weight cap" : `${percent.format(report.constraints.max_weight)} per-stock cap`}; no guarantee of future results.
    </aside>
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
          <rect x={x(item.metrics.volatility) - 6} y={y(item.metrics.expected_return) - 6} width="12" height="12" fill={colors[item.id]} stroke={item.id === baselineId ? "#123d2c" : "white"} strokeWidth={item.id === baselineId ? "3" : "1.5"} />
          <text x={x(item.metrics.volatility) + 9} y={y(item.metrics.expected_return) - 9} fontSize="12" fill={colors[item.id]}>{index + 1}</text>
          <title>{labels[item.id]}: return {percent.format(item.metrics.expected_return)}, volatility {percent.format(item.metrics.volatility)}</title>
        </g>)}
        {report.frontier.profiles.map((item) => {
          const p = report.frontier.points.find((candidate) => candidate.id === item.point_id)!;
          return <g key={item.name}><circle cx={x(p.metrics.volatility)} cy={y(p.metrics.expected_return)} r={selected === item.name ? 9 : 5} fill={selected === item.name ? "#123d2c" : "white"} stroke="#236449" strokeWidth="2"><title>{labels[item.name]}</title></circle>{selected === item.name && <text x={x(p.metrics.volatility) + 12} y={y(p.metrics.expected_return) + 4} className="selected-chart-label">Selected</text>}</g>;
        })}
      </svg></div>
      <div className="chart-legend"><span><i style={{ background: "#236449" }} />Efficient frontier · circles: profiles</span>
        {report.references.map((item, index) => <span key={item.id}><i style={{ background: colors[item.id] }} />{index + 1}. {labels[item.id]}</span>)}
      </div>
    </figure>
    <section className="data-card"><h3>Comparable annual estimates</h3><div className="table-scroll"><table aria-label="Risk and return comparison"><thead><tr><th>Portfolio</th><th>Estimated return</th><th>Estimated volatility</th><th>Constraints</th></tr></thead><tbody>
      <tr><th>{labels[selected]}</th><td>{percent.format(point.metrics.expected_return)}</td><td>{percent.format(point.metrics.volatility)}</td><td>Valid</td></tr>
      {report.references.map((item) => <tr key={item.id}><th>{labels[item.id]}</th><td>{percent.format(item.metrics.expected_return)}</td><td>{percent.format(item.metrics.volatility)}</td><td>{item.constraint_status === "valid" ? "Valid" : item.constraint_status === "exceeds_max_weight" ? "Exceeds weight cap" : "Reference only; outside investable stocks"}</td></tr>)}
    </tbody></table></div></section>
    <SimulationResults stale={stale} report={report} selected={selected} capital={capital ?? report.holdings_capital ?? null} />
    {report.expected_return_comparison && <ReturnComparison comparison={report.expected_return_comparison} />}
    <details ref={advanced} className="details-card"><summary>Advanced recommendation details</summary>
      <section aria-labelledby="allocation-facts-title"><h3 id="allocation-facts-title">Full allocations and structured facts</h3>
        <div className="table-scroll allocation-scroll"><table aria-label="Complete allocation"><thead><tr><th>Asset</th><th>{labels[baselineId]} weight</th><th>{labels[selected]} weight</th><th>Change (pp)</th>{dollars && <th>Amount (USD)</th>}</tr></thead><tbody>{allocationRows.map(({ asset, index, previous, target, change }) => <tr key={asset}><th>{asset}</th><td>{percent.format(previous)}</td><td>{percent.format(target)}</td><td>{signed.format(100 * change)}</td>{dollars && <td>{usd.format(Number(dollars[index].amount))}</td>}</tr>)}</tbody></table></div>
        <ul>{selectedFacts.map((fact) => <li id={`fact-${fact.id}`} key={fact.id}>{factText(fact)}</li>)}</ul>
      </section>
      <section aria-labelledby="models-assumptions-title"><h3 id="models-assumptions-title">Models, assumptions, and estimator diagnostics</h3>
        <p>{report.expected_return_model.estimator_name} · {report.risk_model.estimator_name}</p>
        <ul>{report.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
        {report.diagnostics.length ? <ul>{report.diagnostics.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No model diagnostics were reported.</p>}
        <pre>{JSON.stringify({ expected_return: report.expected_return_model, risk: report.risk_model, benchmark_expected_return: report.benchmark_expected_return_model, benchmark_risk: report.benchmark_risk_model }, null, 2)}</pre>
      </section>
      <section aria-labelledby="coverage-provenance-title"><h3 id="coverage-provenance-title">Data coverage and provenance</h3>
        <pre>{JSON.stringify({ window: report.window, universe: report.universe_provenance, prices: report.price_provenance }, null, 2)}</pre>
      </section>
      <section aria-labelledby="solver-reproducibility-title"><h3 id="solver-reproducibility-title">Solver and reproducibility details</h3>
        <p>Mapping: {report.profile_configuration.version} · {report.profile_configuration.fractions.map((value) => percent.format(value)).join(" / ")}. Maximum weight: {report.constraints.max_weight === null ? "No additional cap" : percent.format(report.constraints.max_weight)}.</p>
        <div className="table-scroll"><table><thead><tr><th>Point</th><th>Estimated annual return</th><th>Estimated annual volatility</th></tr></thead><tbody>{report.frontier.points.map((item) => <tr key={item.id}><th>{item.id}</th><td>{percent.format(item.metrics.expected_return)}</td><td>{percent.format(item.metrics.volatility)}</td></tr>)}</tbody></table></div>
        <pre>{JSON.stringify({ conventions: report.conventions, solvers: report.frontier.points.map((item) => ({ point: item.id, ...item.solver })) }, null, 2)}</pre>
        <p className="fine-print">Report: {report.report_hash}</p>
      </section>
    </details>
  </section>;
}
