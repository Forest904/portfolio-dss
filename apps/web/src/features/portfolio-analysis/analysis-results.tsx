import { PerformanceChart } from "./performance-chart";
import type { ConcentrationSummary, PerformanceSummary, PortfolioAnalysis } from "./types";
import { SectionHeading } from "@/components/presentation";

const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 });
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

function Metric({ label, value }: { label: string; value: string }) {
  return <article className="metric"><span>{label}</span><strong>{value}</strong></article>;
}

function Concentration({ title, value }: { title: string; value: ConcentrationSummary }) {
  return (
    <article className="data-card">
      <h3>{title}</h3>
      <p className="supporting-copy">Largest: {value.largest_id} ({percent.format(value.largest_weight)}) · Effective count: {value.effective_count.toFixed(2)}</p>
      <div className="weight-list">
        {value.components.map((component) => (
          <div key={component.id}>
            <span>{component.id}</span><span>{percent.format(component.weight)}</span>
            <div><i style={{ width: percent.format(component.weight) }} /></div>
          </div>
        ))}
      </div>
      <p className="fine-print">Top three {percent.format(value.top_three_weight)} · HHI {value.hhi.toFixed(4)}</p>
    </article>
  );
}

function PerformanceRow({ name, value }: { name: string; value: PerformanceSummary }) {
  return <tr><th>{name}</th><td>{percent.format(value.total_return)}</td><td>{percent.format(value.annualized_return)}</td><td>{percent.format(value.annualized_volatility)}</td></tr>;
}

export function AnalysisResults({ report }: { report: PortfolioAnalysis }) {
  return (
    <div className="analysis-results" aria-live="polite">
      <SectionHeading eyebrow="Historical analysis" title="Portfolio snapshot">
        <p>{report.window.effective_start} — {report.window.effective_end} · {report.window.return_observations} daily returns</p>
      </SectionHeading>
      <section className="metrics-grid" aria-label="Current portfolio metrics">
        <Metric label={`Value on ${report.valuation.valued_on}`} value={money.format(Number(report.valuation.total_market_value.amount))} />
        <Metric label="Total return" value={percent.format(report.performance.current.total_return)} />
        <Metric label="Annualized return (CAGR)" value={percent.format(report.performance.current.annualized_return)} />
        <Metric label="Annualized volatility" value={percent.format(report.performance.current.annualized_volatility)} />
      </section>
      <PerformanceChart points={report.series} />
      <section className="data-card">
        <h3>Comparable historical performance</h3>
        <div className="table-scroll"><table><thead><tr><th>Portfolio</th><th>Total return</th><th>Annualized return</th><th>Annualized volatility</th></tr></thead><tbody>
          <PerformanceRow name="Current" value={report.performance.current} />
          <PerformanceRow name="Equal weight" value={report.performance.equal_weight} />
          <PerformanceRow name="S&P 500 (SPY ETF proxy)" value={report.performance.sp500_proxy} />
        </tbody></table></div>
      </section>
      <section className="split-grid">
        <Concentration title="Holding concentration" value={report.concentration.assets} />
        <Concentration title="Sector concentration" value={report.concentration.sectors} />
      </section>
      <section className="data-card">
        <h3>Asset correlation</h3>
        <p className="supporting-copy">Pearson correlation from aligned daily returns. N/A means correlation is undefined because an asset had no observed volatility.</p>
        <div className="table-scroll"><table className="matrix"><thead><tr><th>Asset</th>{report.correlation.asset_ids.map((asset) => <th key={asset}>{asset}</th>)}</tr></thead><tbody>
          {report.correlation.values.map((row, rowIndex) => <tr key={report.correlation.asset_ids[rowIndex]}><th>{report.correlation.asset_ids[rowIndex]}</th>{row.map((value, columnIndex) => <td key={report.correlation.asset_ids[columnIndex]} style={value === null ? undefined : { backgroundColor: `rgba(35, 100, 73, ${Math.abs(value) * 0.3})` }}>{value === null ? "N/A" : value.toFixed(3)}</td>)}</tr>)}
        </tbody></table></div>
      </section>
      <details className="details-card"><summary>Advanced data and assumptions</summary>
        <h3>Data quality</h3>
        <p className="supporting-copy">{report.window.aligned_price_observations} common prices produced {report.window.return_observations} returns. Excluded observations before intersection: {report.window.excluded_observations.map((item) => `${item.asset_id} ${item.count}`).join(" · ") || "none"}.</p>
        <h3>Annualized covariance</h3>
        <div className="table-scroll"><table className="matrix"><thead><tr><th>Asset</th>{report.covariance.asset_ids.map((asset) => <th key={asset}>{asset}</th>)}</tr></thead><tbody>{report.covariance.values.map((row, rowIndex) => <tr key={report.covariance.asset_ids[rowIndex]}><th>{report.covariance.asset_ids[rowIndex]}</th>{row.map((value, columnIndex) => <td key={report.covariance.asset_ids[columnIndex]}>{value?.toPrecision(5) ?? "N/A"}</td>)}</tr>)}</tbody></table></div>
        {report.diagnostics.length > 0 && <><h3>Diagnostics</h3><ul>{report.diagnostics.map((item) => <li key={item}>{item}</li>)}</ul></>}
        <h3>Assumptions</h3><ul>{report.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
        <p className="fine-print">Price source: {report.provenance.price_data.provider} · Retrieved {report.provenance.price_data.retrieved_at} · Analysis {report.analysis_hash}</p>
      </details>
    </div>
  );
}
