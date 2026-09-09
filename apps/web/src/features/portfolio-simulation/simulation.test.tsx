import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import frontierFixture from "../portfolio-frontier/__fixtures__/frontier.json";
import guidedFixture from "../guided-builder/__fixtures__/completed.json";
import type { FrontierReport } from "../portfolio-frontier/types";
import { FrontierResults } from "../portfolio-frontier/frontier-results";
import { SimulationResults } from "./simulation-results";
import simulationFixture from "./__fixtures__/simulation.json";
import { scenarioFromReport } from "./types";

const report = { ...frontierFixture, holdings_capital: "10000" } as unknown as FrontierReport;
const response = () => new Response(JSON.stringify(simulationFixture));
afterEach(() => vi.restoreAllMocks());

describe("Simulation comparison", () => {
  it("opens lazily, follows profiles, switches benchmarks and reuses distributions", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => response());
    render(<FrontierResults report={report} />);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Explore uncertainty" }));
    await screen.findByRole("table", { name: "Terminal simulation metrics" });
    const sent = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).scenario;
    expect(sent.initial_capital).toBe(10000);
    expect(sent.portfolios).toHaveLength(6);
    expect(sent.configuration).toEqual({ horizon_years: 1, paths: 10000, seed: 42 });
    expect(screen.getByRole("img", { name: "Current portfolio 1-year percentile fan, USD" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /^Aggressive/ }));
    expect(screen.getByRole("img", { name: "Aggressive 1-year percentile fan, USD" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Compare with"), { target: { value: "sp500_proxy" } });
    expect(screen.getByRole("img", { name: /SPY ETF proxy.*percentile fan/ })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Simulation horizon"), { target: { value: "3" } });
    expect(screen.getByText(/Results are stale/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Simulation horizon"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Loss means finishing below starting nominal capital/)).toBeInTheDocument();
  });

  it("sends advanced settings, rejects a late response and retries errors", async () => {
    let resolve!: (value: Response) => void;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => new Promise((r) => { resolve = r; }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "Try another seed" }), { status: 422 }))
      .mockImplementation(async () => response());
    render(<SimulationResults report={report} selected="moderate" capital="10000" />);
    fireEvent.click(screen.getByRole("button", { name: "Explore uncertainty" }));
    fireEvent.change(screen.getByLabelText("Random seed"), { target: { value: "123" } });
    fireEvent.change(screen.getByLabelText("Simulated paths"), { target: { value: "50000" } });
    await act(async () => resolve(response()));
    expect(screen.queryByRole("table", { name: "Terminal simulation metrics" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Try another seed");
    const sent = JSON.parse(String(fetchMock.mock.calls[1][1]?.body)).scenario;
    expect(sent.configuration).toEqual({ horizon_years: 1, paths: 50000, seed: 123 });
    fireEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    await screen.findByRole("table", { name: "Terminal simulation metrics" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("uses guided capital and equal-weight comparison without inventing holdings", async () => {
    const guided = guidedFixture.report!.model.report as unknown as FrontierReport;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => response());
    render(<FrontierResults report={guided} capital="25000" suggestedProfile="moderate" />);
    fireEvent.click(screen.getByRole("button", { name: "Explore uncertainty" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const sent = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).scenario;
    expect(sent.initial_capital).toBe(25000);
    expect(sent.portfolios.map((p: { id: string }) => p.id)).not.toContain("current");
    expect(sent.portfolios).toHaveLength(5);
    expect(screen.getByLabelText("Compare with")).toHaveValue("equal_weight");
  });

  it("keeps benchmark estimates and shared conventions in the compact scenario", () => {
    const scenario = scenarioFromReport(report, "12000", { horizon_years: 5, paths: 1000, seed: 0 });
    const benchmark = scenario.portfolios.find((p) => p.id === "sp500_proxy")!;
    expect(benchmark.annual_mean).toBe(report.references.find((p) => p.id === "sp500_proxy")!.metrics.expected_return);
    expect(benchmark.metadata.return_estimator).toBe(report.benchmark_expected_return_model.estimator_name);
    expect(new Set(scenario.portfolios.map((p) => p.metadata.estimation_start)).size).toBe(1);
    expect(() => scenarioFromReport({ ...report, risk_model: { ...report.risk_model, observations: 1 } }, "10000", scenario.configuration)).toThrow(/conventions/);
  });
});
