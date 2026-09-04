"use client";

import { FormEvent, useState } from "react";

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

  const updatePosition = (id: number, field: "ticker" | "quantity", value: string) => {
    setPositions((current) => current.map((position) => position.id === id ? { ...position, [field]: value } : position));
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const history = start || end ? { ...(start && { start }), ...(end && { end }) } : undefined;
      const response = await fetch("/api/portfolio-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ positions: positions.map(({ ticker, quantity }) => ({ ticker, quantity })), ...(history && { history }) }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) {
        const candidate = payload as Partial<AnalysisError>;
        throw { code: candidate.code ?? "ANALYSIS_FAILED", message: candidate.message ?? "The portfolio could not be analyzed." } satisfies AnalysisError;
      }
      setReport(payload as PortfolioAnalysis);
    } catch (reason) {
      const candidate = reason as Partial<AnalysisError>;
      setError({ code: candidate.code ?? "ANALYSIS_FAILED", message: candidate.message ?? "The portfolio could not be analyzed." });
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="analysis-workspace" aria-labelledby="analysis-title">
      <div className="workspace-intro"><p className="eyebrow">Week 3 · Historical analytics</p><h2 id="analysis-title">Analyze your current portfolio</h2><p>Enter current quantities. The comparison uses observed adjusted-close history—not a prediction.</p></div>
      <form onSubmit={submit} className="portfolio-form">
        <fieldset><legend>Holdings</legend>
          {positions.map((position, index) => <div className="position-row" key={position.id}>
            <label>Ticker <input aria-label={`Ticker ${index + 1}`} required value={position.ticker} onChange={(event) => updatePosition(position.id, "ticker", event.target.value.toUpperCase())} /></label>
            <label>Quantity <input aria-label={`Quantity ${index + 1}`} required min="0.00000001" step="any" type="number" value={position.quantity} onChange={(event) => updatePosition(position.id, "quantity", event.target.value)} /></label>
            <button type="button" className="text-button" disabled={positions.length === 1} onClick={() => setPositions((current) => current.filter((item) => item.id !== position.id))}>Remove</button>
          </div>)}
          <button type="button" className="secondary-button" onClick={() => { setPositions((current) => [...current, { id: nextId, ticker: "", quantity: "" }]); setNextId((value) => value + 1); }}>Add holding</button>
        </fieldset>
        <fieldset><legend>History window <span>optional</span></legend><div className="date-row"><label>Start date <input type="date" value={start} onChange={(event) => setStart(event.target.value)} /></label><label>End date <input type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></label></div><p className="fine-print">Blank dates use the latest completed session and the preceding three calendar years.</p></fieldset>
        <button className="primary-button" disabled={loading} type="submit">{loading ? "Analyzing…" : "Analyze portfolio"}</button>
        {error && <div role="alert" className="error-card"><strong>{error.code}</strong><span>{error.message}</span></div>}
      </form>
      {report && <AnalysisResults report={report} />}
    </section>
  );
}
