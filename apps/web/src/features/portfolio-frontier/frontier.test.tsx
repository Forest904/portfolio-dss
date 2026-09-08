import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PortfolioAnalysisWorkspace } from "../portfolio-analysis/portfolio-analysis";
import fixture from "./__fixtures__/frontier.json";
import { FrontierResults } from "./frontier-results";
import type { FrontierReport, ProfileName } from "./types";

// Captured from the real API using deterministic synthetic price providers.
const report = fixture as unknown as FrontierReport;
const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 });
const response = () => new Response(JSON.stringify(report), { status: 200 });

afterEach(() => vi.restoreAllMocks());

describe("Frontier decision workspace", () => {
  it("submits constraints, selects all profiles, and changes allocations, metrics and facts without fetching again", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => response());
    render(<PortfolioAnalysisWorkspace />);
    fireEvent.change(screen.getByLabelText("Maximum weight per stock (%)"), { target: { value: "60" } });
    fireEvent.click(screen.getByRole("button", { name: "Compare alternatives" }));
    await screen.findByRole("heading", { name: "Explore the trade-off" });
    expect(fetchMock).toHaveBeenCalledWith("/api/portfolio-frontier", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).constraints.max_weight).toBe(0.6);
    expect(screen.getByRole("radio", { name: /^Moderate/ })).toBeChecked();
    for (const name of ["conservative", "moderate", "aggressive"] as ProfileName[]) {
      const label = name[0].toUpperCase() + name.slice(1);
      fireEvent.click(screen.getByRole("radio", { name: new RegExp(`^${label}`) }));
      expect(screen.getByRole("radio", { name: new RegExp(`^${label}`) })).toBeChecked();
      const profile = report.frontier.profiles.find((item) => item.name === name)!;
      const point = report.frontier.points.find((item) => item.id === profile.point_id)!;
      const metrics = within(screen.getByLabelText("Selected alternative metrics"));
      expect(metrics.getByText(percent.format(point.metrics.expected_return))).toBeInTheDocument();
      expect(metrics.getByText(percent.format(point.metrics.volatility))).toBeInTheDocument();
      const allocations = within(screen.getByRole("table", { name: "Allocation comparison" }));
      expect(allocations.getByRole("columnheader", { name: `${label} weight` })).toBeInTheDocument();
      const assetRow = within(allocations.getByRole("row", { name: /^AAPL / }));
      expect(assetRow.getAllByRole("cell")[1]).toHaveTextContent(percent.format(point.weights.weights[0]));
      expect(screen.getByRole("heading", { name: `Decision facts · ${label}` })).toBeInTheDocument();
      const fact = report.facts.find((item) => item.id === `${name}.current.expected_return_change`)!;
      const signed = new Intl.NumberFormat("en-US", { signDisplay: "exceptZero", maximumFractionDigits: 2 }).format(fact.value);
      expect(screen.getByText(`Estimated annual return: ${signed} percentage points versus Current portfolio.`)).toBeInTheDocument();
    }
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("group", { name: "Risk preference" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /annual risk and return frontier/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Assumptions" })).toBeInTheDocument();
  });

  it.each(["Ticker 1", "Quantity 1", "Start date", "End date", "Maximum weight per stock (%)"])("invalidates results when %s changes", async (label) => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => response());
    render(<PortfolioAnalysisWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "Compare alternatives" }));
    await screen.findByRole("heading", { name: "Explore the trade-off" });
    const value = label.includes("date") ? "2025-01-01" : label.includes("Ticker") ? "NVDA" : "5";
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
    expect(screen.queryByRole("heading", { name: "Explore the trade-off" })).not.toBeInTheDocument();
  });

  it("ignores an old response after edits and a new request", async () => {
    let resolveOld!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => { resolveOld = resolve; });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockReturnValueOnce(pending).mockImplementationOnce(async () => response());
    render(<PortfolioAnalysisWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "Compare alternatives" }));
    fireEvent.change(screen.getByLabelText("Quantity 1"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Compare alternatives" }));
    await screen.findByRole("heading", { name: "Explore the trade-off" });
    await act(async () => { resolveOld(new Response(JSON.stringify({ code: "OLD_ERROR", message: "Stale request" }), { status: 500 })); });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Explore the trade-off" })).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true);
  });

  it("shows API failures and allows retry", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({ code: "INFEASIBLE_CONSTRAINTS", message: "The maximum weight cannot fund the portfolio." }), { status: 422 })).mockImplementationOnce(async () => response());
    render(<PortfolioAnalysisWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "Compare alternatives" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("INFEASIBLE_CONSTRAINTS");
    fireEvent.click(screen.getByRole("button", { name: "Compare alternatives" }));
    await screen.findByRole("heading", { name: "Explore the trade-off" });
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });

  it("renders coincident profiles, negative returns, and a single-point chart", () => {
    const collapsed = structuredClone(report);
    collapsed.frontier.points = [collapsed.frontier.points[0]];
    collapsed.frontier.points[0].metrics.expected_return = -0.04;
    collapsed.frontier.points[0].metrics.volatility = 0;
    collapsed.frontier.profiles.forEach((item) => { item.point_id = collapsed.frontier.points[0].id; });
    render(<FrontierResults report={collapsed} />);
    expect(screen.getByRole("status")).toHaveTextContent("Some profiles coincide");
    expect(within(screen.getByLabelText("Selected alternative metrics")).getByText("-4%")).toBeInTheDocument();
    expect(screen.getByRole("img").innerHTML).not.toMatch(/NaN|Infinity/);
    fireEvent.click(screen.getByRole("radio", { name: /^Aggressive/ }));
    expect(screen.getByRole("heading", { name: "Allocation: current vs Aggressive" })).toBeInTheDocument();
  });
});
