import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PortfolioAnalysisWorkspace } from "./portfolio-analysis";
import type { PortfolioAnalysis } from "./types";

const report: PortfolioAnalysis = {
  valuation: {
    valued_on: "2026-09-03",
    total_market_value: { amount: "1800", currency: "USD" },
    positions: [],
  },
  window: {
    requested_start: "2023-09-04",
    requested_end: "2026-09-04",
    effective_start: "2023-09-05",
    effective_end: "2026-09-03",
    aligned_price_observations: 754,
    return_observations: 753,
    excluded_observations: [],
  },
  series: [
    { date: "2023-09-05", current: { daily_return: null, cumulative_return: 0 }, equal_weight: { daily_return: null, cumulative_return: 0 }, sp500_proxy: { daily_return: null, cumulative_return: 0 } },
    { date: "2026-09-03", current: { daily_return: 0.01, cumulative_return: 0.2 }, equal_weight: { daily_return: 0.009, cumulative_return: 0.18 }, sp500_proxy: { daily_return: 0.008, cumulative_return: 0.16 } },
  ],
  performance: {
    current: { total_return: 0.2, annualized_return: 0.063, annualized_volatility: 0.15 },
    equal_weight: { total_return: 0.18, annualized_return: 0.057, annualized_volatility: 0.14 },
    sp500_proxy: { total_return: 0.16, annualized_return: 0.051, annualized_volatility: 0.13 },
    current_vs_sp500_annualized_return: 0.012,
    current_vs_sp500_annualized_volatility: 0.02,
    equal_weight_vs_sp500_annualized_return: 0.006,
    equal_weight_vs_sp500_annualized_volatility: 0.01,
  },
  covariance: { asset_ids: ["AAPL", "MSFT"], values: [[0.03, 0.01], [0.01, 0.02]], estimator: "sample_covariance" },
  correlation: { asset_ids: ["AAPL", "MSFT"], values: [[1, null], [null, null]], estimator: "pearson_sample_correlation" },
  concentration: {
    assets: { components: [{ id: "AAPL", weight: 0.6 }, { id: "MSFT", weight: 0.4 }], largest_id: "AAPL", largest_weight: 0.6, top_three_weight: 1, hhi: 0.52, effective_count: 1.923 },
    sectors: { components: [{ id: "Technology", weight: 1 }], largest_id: "Technology", largest_weight: 1, top_three_weight: 1, hhi: 1, effective_count: 1 },
  },
  provenance: { universe: { as_of: "2026-09-04", provenance: { provider: "fixture", content_hash: "u" } }, price_data: { provider: "fixture", retrieved_at: "2026-09-04T20:00:00Z", content_hash: "p", stale_fallback: false } },
  assumptions: ["Observed history, not a forecast"],
  diagnostics: ["Undefined correlations for MSFT."],
  analysis_hash: "abc123",
};

afterEach(() => vi.restoreAllMocks());

describe("PortfolioAnalysisWorkspace", () => {
  it("adds and removes holding inputs", () => {
    render(<PortfolioAnalysisWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: /add holding/i }));
    expect(screen.getByLabelText("Ticker 3")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: /remove/i })[2]);
    expect(screen.queryByLabelText("Ticker 3")).not.toBeInTheDocument();
  });

  it("submits positions and renders labelled historical results", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(report), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    render(<PortfolioAnalysisWorkspace />);
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2023-09-04" } });
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-09-04" } });
    fireEvent.click(screen.getByRole("button", { name: /analyze portfolio/i }));

    await screen.findByText("Portfolio snapshot");
    expect(screen.getByText("Annualized return (CAGR)")).toBeInTheDocument();
    expect(screen.getAllByText("S&P 500 (SPY ETF proxy)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("N/A").length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledWith("/api/portfolio-analysis", expect.objectContaining({ method: "POST" }));
    const request = fetchMock.mock.calls[0][1];
    expect(JSON.parse(String(request?.body))).toMatchObject({
      positions: [{ ticker: "AAPL", quantity: "10" }, { ticker: "MSFT", quantity: "4" }],
      history: { start: "2023-09-04", end: "2026-09-04" },
    });
  });

  it("shows machine-readable API errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ code: "INSUFFICIENT_HISTORY", message: "Not enough aligned history." }), { status: 422 }));
    render(<PortfolioAnalysisWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: /analyze portfolio/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("INSUFFICIENT_HISTORY"));
  });
});
