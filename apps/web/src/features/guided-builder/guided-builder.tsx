"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { PortfolioAnalysisWorkspace } from "../portfolio-analysis/portfolio-analysis";
import { FrontierResults } from "../portfolio-frontier/frontier-results";
import type { ProfileName } from "../portfolio-frontier/types";
import type { Answers, GuidedJob, GuidedReport, QuestionId } from "./types";

import { EstimatorSelector } from "../expected-returns/estimator-selector";
import type { EstimatorId } from "../expected-returns/types";

const profiles: ProfileName[] = ["conservative", "moderate", "aggressive"];
const questions: { id: QuestionId; title: string; choices: string[] }[] = [
  { id: "trade_off", title: "Which trade-off do you prefer?", choices: ["Prioritize smaller fluctuations", "Balance growth and fluctuations", "Pursue higher estimated growth with larger fluctuations"] },
  { id: "fluctuations", title: "How comfortable are you with portfolio values changing substantially?", choices: ["Uncomfortable", "Somewhat comfortable", "Comfortable"] },
  { id: "decline", title: "In a hypothetical substantial decline, which response best describes you?", choices: ["Prefer reducing exposure", "Reassess before changing exposure", "Accept continued exposure despite possible further losses"] },
];
const stages: Record<string, string> = { queued: "Waiting to calculate", loading_universe: "Loading current S&P 500 constituents", loading_prices: "Loading historical prices", checking_coverage: "Checking stock data coverage", calculating_alternatives: "Calculating portfolio alternatives" };

export function PortfolioWorkspace() {
  const [journey, setJourney] = useState<"build" | "analyze">("build");
  return <>
    <nav className="journey-switch" aria-label="Portfolio journey">
      <button className="journey-option" aria-label="Build a portfolio" aria-pressed={journey === "build"} onClick={() => setJourney("build")}>
        <span className="journey-number" aria-hidden="true">01</span>
        <span><strong>Build a portfolio</strong><small>Start with your capital and preferences.</small></span>
      </button>
      <button className="journey-option" aria-label="Analyze existing holdings" aria-pressed={journey === "analyze"} onClick={() => setJourney("analyze")}>
        <span className="journey-number" aria-hidden="true">02</span>
        <span><strong>Analyze existing holdings</strong><small>Review history and compare alternatives.</small></span>
      </button>
    </nav>
    <div hidden={journey !== "build"}><GuidedBuilder active={journey === "build"} /></div>
    {journey === "analyze" && <PortfolioAnalysisWorkspace />}
  </>;
}

export function GuidedBuilder({ active = true }: { active?: boolean }) {
  const [estimator, setEstimator] = useState<EstimatorId>("historical_mean");
  const [stale, setStale] = useState(false);
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Partial<Answers>>({});
  const [capital, setCapital] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [stage, setStage] = useState("queued");
  const [report, setReport] = useState<GuidedReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [validation, setValidation] = useState("");
  const revision = useRef(0);
  const submitController = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const hasMounted = useRef(false);
  const suggested = profiles.find((p) => Object.values(answers).includes(p));
  const complete = questions.every((q) => answers[q.id]);

  useEffect(() => {
    if (!hasMounted.current) { hasMounted.current = true; return; }
    heading.current?.focus({ preventScroll: true });
  }, [step]);
  useEffect(() => () => { revision.current++; submitController.current?.abort(); }, []);
  useEffect(() => {
    if (!active || step !== 2 || !jobId || report || error) return;
    const controller = new AbortController();
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const version = revision.current;
    async function poll() {
      try {
        const response = await fetch(`/api/guided-recommendations/${jobId}`, { signal: controller.signal, cache: "no-store" });
        const payload = await response.json();
        if (disposed || revision.current !== version) return;
        if (!response.ok) throw new Error(payload.message ?? "Could not check the calculation.");
        const job = payload as GuidedJob;
        setStage(job.stage);
        if (job.status === "completed" && job.report) { setReport(job.report); setStale(false); }
        else if (job.status === "failed") setError(job.error?.message ?? "The calculation failed. Please retry.");
        else timer = setTimeout(poll, 2000);
      } catch (reason) {
        if (!disposed && revision.current === version) setError(reason instanceof Error ? reason.message : "Could not check the calculation. Please retry.");
      }
    }
    void poll();
    return () => { disposed = true; controller.abort(); clearTimeout(timer); };
  }, [active, step, jobId, report, error]);

  function invalidate() {
    revision.current++;
    submitController.current?.abort();
    setSubmitting(false); setJobId(null); setReport(null); setError(null); setValidation("");
  }

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!complete) {
      setValidation("Answer all three preference questions before continuing.");
      requestAnimationFrame(() => document.querySelector<HTMLElement>('.profile-controls[aria-invalid="true"] input')?.focus());
      return;
    }
    if (!/^\d+(\.\d{1,2})?$/.test(capital) || !Number.isFinite(Number(capital)) || Number(capital) <= 0) {
      setValidation("Enter positive USD capital with at most two decimal places.");
      requestAnimationFrame(() => document.querySelector<HTMLElement>("#guided-capital")?.focus());
      return;
    }
    invalidate();
    const version = revision.current;
    const controller = new AbortController();
    submitController.current = controller;
    setSubmitting(true); setStep(2); setStage("queued");
    try {
      const response = await fetch("/api/guided-recommendations", { method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
        body: JSON.stringify({ version: "guided-preferences-v1", answers, capital, expected_return_estimator: estimator }) });
      const payload = await response.json();
      if (version !== revision.current) return;
      if (!response.ok) throw new Error(payload.message ?? "Could not start the calculation.");
      setJobId(payload.id);
    } catch (reason) {
      if (version === revision.current) setError(reason instanceof Error ? reason.message : "Could not start the calculation.");
    } finally { if (version === revision.current) setSubmitting(false); }
  }

  return <section className="analysis-workspace guided-builder" aria-labelledby="builder-title">
    <div className="workspace-intro"><p className="eyebrow">Guided portfolio construction</p><h2 id="builder-title">Build from your preferences</h2>
      <p>Explore an allocation across eligible S&P 500 stocks. No tickers or mathematical settings needed.</p></div>
    <ol className="guided-steps" aria-label="Builder progress">{["Preferences", "Capital and review", "Recommendation"].map((label, index) => <li key={label} className={index < step ? "complete" : undefined} aria-current={step === index ? "step" : undefined}><span aria-hidden="true">{index < step ? "✓" : index + 1}</span>{label}</li>)}</ol>
    <h3 ref={heading} tabIndex={-1}>{["Tell us your preferences", "Review your starting point", "Your recommendation"][step]}</h3>
    {step === 0 && <form noValidate className="portfolio-form" onSubmit={(e) => { e.preventDefault(); if (complete) { setValidation(""); setStep(1); } else { setValidation("Answer all three preference questions before continuing."); requestAnimationFrame(() => document.querySelector<HTMLElement>('.profile-controls[aria-invalid="true"] input')?.focus()); } }}>
      {questions.map((q) => <fieldset aria-invalid={Boolean(validation && !answers[q.id])} className="profile-controls" key={q.id}><legend>{q.title}</legend>{q.choices.map((choice, i) => <label className={answers[q.id] === profiles[i] ? "profile-option selected" : "profile-option"} key={choice}>
        <input required type="radio" name={q.id} value={profiles[i]} checked={answers[q.id] === profiles[i]} onChange={() => { invalidate(); setAnswers((a) => ({ ...a, [q.id]: profiles[i] })); }} /><span>{choice}</span>
      </label>)}</fieldset>)}
      {validation && <p className="field-error" role="alert">{validation}</p>}
      <p className="fine-print">Your lowest expressed tolerance determines the suggestion. This is an educational preference input, not a suitability assessment.</p>
      <button className="primary-button" type="submit">Continue to capital</button>
    </form>}
    {step === 1 && <form noValidate className="portfolio-form" onSubmit={submit}>
      <label>Investable capital (USD)<input id="guided-capital" aria-invalid={Boolean(validation)} aria-describedby={validation ? "capital-error" : undefined} required inputMode="decimal" type="text" pattern="[0-9]+(\.[0-9]{1,2})?" value={capital} onChange={(e) => { invalidate(); setCapital(e.target.value); }} /></label>
      {validation && <p id="capital-error" className="field-error" role="alert">{validation}</p>}
      <EstimatorSelector value={estimator} onChange={(value) => {
        revision.current++; submitController.current?.abort(); setSubmitting(false); setJobId(null); setError(null);
        setEstimator(value); setStale(true);
      }} />
      <div className="data-card"><h4>Questionnaire suggestion: {suggested}</h4><p>Determined by: {questions.filter((q) => answers[q.id] === suggested).map((q) => q.title).join("; ")}</p>
        <p>We screen all current S&P 500 constituents and disclose exclusions. At least 90% must have complete prices on the observed SPY sessions. Each stock is limited to 10% of the allocation.</p>
        <p>We estimate annual return and volatility from the preceding three calendar years of adjusted-close prices. This history window is not an investment horizon.</p>
        <p>All profiles are stocks-only. Conservative does not mean capital protection. Capital scales illustrative USD amounts; costs, taxes and share purchases are excluded.</p></div>
      <div className="result-views"><button type="button" className="secondary-button" onClick={() => setStep(0)}>Back to preferences</button><button className="primary-button" type="submit" disabled={submitting}>Get recommendation</button></div>
    </form>}
    {stale && report && <p className="inline-notice warning" role="status">Recommendations and simulations are stale. Use Get recommendation to recalculate with the chosen estimator. Displayed values retain their original model.</p>}
    {error && <div role="alert" className="error-card"><span>{error}</span>{step === 2 && <button className="secondary-button" onClick={() => void submit()}>Retry calculation</button>}</div>}
    {step === 2 && <>
      <button className="secondary-button" onClick={() => { if (submitting) invalidate(); setStep(1); }}>Back to capital and review</button>
      {!report && !error && <div role="status" className="data-card"><strong>{stages[stage] ?? "Preparing recommendation"}</strong><p>A full-universe calculation can take several minutes. You can return to review while it runs.</p></div>}
      {report && <GuidedResults report={report} stale={stale} />}
    </>}
  </section>;
}

function GuidedResults({ report, stale = false }: { report: GuidedReport; stale?: boolean }) {
  const { coverage } = report.model;
  return <>
    <section className="data-card"><h3>Your starting point</h3><p>{report.preference.explanation}</p><p>Capital: {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(report.capital))} USD. Fully invested target weights, at most 10% per stock.</p>
      <p>{coverage.eligible} of {coverage.total} current constituent tickers qualify. Membership date: {report.model.report.universe_as_of}. All comparisons share {report.model.report.window.effective_start} to {report.model.report.window.effective_end}.</p>
      <p>Estimated annual values are not guaranteed outcomes. Conservative does not mean capital protection. Current membership introduces survivorship bias.</p>
      {(report.model.report.universe_provenance.stale_fallback || report.model.price_sources.some((p) => p.stale_fallback)) && <p role="status">Cached source data was used after a refresh failed. Check retrieval dates below.</p>}
      <details><summary>Data coverage and source details ({coverage.excluded.length} exclusions)</summary>{coverage.excluded.length ? <ul>{coverage.excluded.map((e) => <li key={e.asset_id}>{e.asset_id}: {e.reason}</li>)}</ul> : <p>No constituents were excluded from this calculation.</p>}<p>Policy: {coverage.policy}. No missing prices are filled.</p><pre>{JSON.stringify(report.model.price_sources, null, 2)}</pre><p>Report: {report.report_hash}</p></details>
    </section>
    <FrontierResults key={report.report_hash} report={report.model.report} stale={stale} capital={report.capital} suggestedProfile={report.preference.suggested_profile} preferenceExplanation={report.preference.explanation} alternatives={report.alternatives} />
  </>;
}
