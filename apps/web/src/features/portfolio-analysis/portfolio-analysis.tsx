"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { FrontierResults } from "../portfolio-frontier/frontier-results";
import type { FrontierReport } from "../portfolio-frontier/types";

import { AnalysisResults } from "./analysis-results";
import type { AnalysisError, PortfolioAnalysis } from "./types";

type PositionInput = { id: number; ticker: string; quantity: string };

export function PortfolioAnalysisWorkspace() {
  const [positions, setPositions] = useState<PositionInput[]>([
    { id: 1, ticker: "AAPL", quantity: "10" },
    { id: 2, ticker: "MSFT", quantity: "4" },
  ]);
  const [nextId, setNextId] = useState(3);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [report, setReport] = useState<PortfolioAnalysis | null>(null);
  const [error, setError] = useState<AnalysisError | null>(null);
  const [loading, setLoading] = useState(false);
  const [maxWeight, setMaxWeight] = useState("");
  const [frontier, setFrontier] = useState<FrontierReport | null>(null);
  const [view, setView] = useState<"analysis" | "frontier">("analysis");
  const requestVersion = useRef(0);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { controller.current?.abort(); requestVersion.current += 1; }, []);

  function invalidate() {
    requestVersion.current += 1;
    controller.current?.abort();
    setLoading(false);
    setReport(null);
    setFrontier(null);
    setError(null);
  }

  const updatePosition = (id: number, field: "ticker" | "quantity", value: string) => {
    setPositions((current) => current.map((position) => position.id === id ? { ...position, [field]: value } : position));
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const mode = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "frontier" ? "frontier" : "analysis";
    const version = ++requestVersion.current;
    controller.current?.abort();
    controller.current = new AbortController();
    setView(mode);
    setLoading(true);
    setError(null);
    try {
      const history = start || end ? { ...(start && { start }), ...(end && { end }) } : undefined;
      const response = await fetch(mode === "frontier" ? "/api/portfolio-frontier" : "/api/portfolio-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ positions: positions.map(({ ticker, quantity }) => ({ ticker, quantity })), ...(history && { history }), ...(mode === "frontier" && maxWeight !== "" && { constraints: { max_weight: Number(maxWeight) / 100 } }) }),
        signal: controller.current.signal,
      });
      const payload: unknown = await response.json();
      if (version !== requestVersion.current) return;
      if (!response.ok) {
        const candidate = payload as Partial<AnalysisError>;
        throw { code: candidate.code ?? (mode === "frontier" ? "FRONTIER_FAILED" : "ANALYSIS_FAILED"), message: candidate.message ?? (mode === "frontier" ? "The alternatives could not be calculated." : "The portfolio could not be analyzed.") } satisfies AnalysisError;
      }
      if (mode === "frontier") setFrontier(payload as FrontierReport);
      else setReport(payload as PortfolioAnalysis);
    } catch (reason) {
      if (version !== requestVersion.current) return;
      const candidate = reason as Partial<AnalysisError>;
      setError({ code: candidate.code ?? (mode === "frontier" ? "FRONTIER_FAILED" : "ANALYSIS_FAILED"), message: candidate.message ?? (mode === "frontier" ? "The alternatives could not be calculated." : "The portfolio could not be analyzed.") });
      if (mode === "frontier") setFrontier(null);
      else setReport(null);
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }

  return (
    <section className="analysis-workspace" aria-labelledby="analysis-title">
      <div className="workspace-intro"><p className="eyebrow">Historical analysis & decision alternatives</p><h2 id="analysis-title">Understand your portfolio choices</h2><p>Enter current quantities to review observed history or compare estimated risk and return across alternative allocations.</p></div>
      <form onSubmit={submit} onChange={invalidate} className="portfolio-form">
        <fieldset><legend>Holdings</legend>
          {positions.map((position, index) => <div className="position-row" key={position.id}>
            <label>Ticker <input aria-label={`Ticker ${index + 1}`} required value={position.ticker} onChange={(event) => updatePosition(position.id, "ticker", event.target.value.toUpperCase())} /></label>
            <label>Quantity <input aria-label={`Quantity ${index + 1}`} required min="0.00000001" step="any" type="number" value={position.quantity} onChange={(event) => updatePosition(position.id, "quantity", event.target.value)} /></label>
            <button type="button" className="text-button" disabled={positions.length === 1} onClick={() => { invalidate(); setPositions((current) => current.filter((item) => item.id !== position.id)); }}>Remove</button>
          </div>)}
          <button type="button" className="secondary-button" onClick={() => { invalidate(); setPositions((current) => [...current, { id: nextId, ticker: "", quantity: "" }]); setNextId((value) => value + 1); }}>Add holding</button>
        </fieldset>
        <fieldset><legend>History window <span>optional</span></legend><div className="date-row"><label>Start date <input type="date" value={start} onChange={(event) => setStart(event.target.value)} /></label><label>End date <input type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></label></div><p className="fine-print">Blank dates use the latest completed session and the preceding three calendar years.</p></fieldset>
        <fieldset><legend>Alternative constraints <span>optional</span></legend><label>Maximum weight per stock (%) <input type="number" min="0.01" max="100" step="any" value={maxWeight} onChange={(event) => setMaxWeight(event.target.value)} /></label><p className="fine-print">Applies to decision alternatives. Blank means no additional cap. Weights must still total 100%.</p></fieldset>
        <button className="secondary-button" disabled={loading} type="submit">{loading && view === "analysis" ? "Analyzing..." : "Analyze portfolio"}</button>
        <button className="primary-button" disabled={loading} type="submit" value="frontier">{loading && view === "frontier" ? "Comparing alternatives…" : "Compare alternatives"}</button>
        {error && <div role="alert" className="error-card"><strong>{error.code}</strong><span>{error.message}</span></div>}
      </form>
      {(report || frontier) && <nav className="result-views" aria-label="Result views">
        {report && <button type="button" className="secondary-button" disabled={loading} aria-pressed={view === "analysis"} onClick={() => setView("analysis")}>Historical analysis</button>}
        {frontier && <button type="button" className="secondary-button" disabled={loading} aria-pressed={view === "frontier"} onClick={() => setView("frontier")}>Decision alternatives</button>}
      </nav>}
      {!loading && view === "analysis" && report && <AnalysisResults report={report} />}
      {!loading && view === "frontier" && frontier && <FrontierResults key={frontier.report_hash} report={frontier} />}
    </section>
  );
}
