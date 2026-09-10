import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import historical from "./__fixtures__/historical_mean.json";
import forecast from "./__fixtures__/simple_forecast.json";
import guided from "../guided-builder/__fixtures__/completed.json";
import { PortfolioAnalysisWorkspace } from "../portfolio-analysis/portfolio-analysis";
import { GuidedBuilder } from "../guided-builder/guided-builder";
import { ReturnComparison } from "./return-comparison";
import type { ExpectedReturnComparison } from "./types";
import type { FrontierReport } from "../portfolio-frontier/types";
import { scenarioFromReport } from "../portfolio-simulation/types";

const json = (payload: unknown) => new Response(JSON.stringify(payload));
afterEach(() => vi.restoreAllMocks());

it("shows annual units, model provenance, diagnostics and paginated assets", () => {
  const comparison = structuredClone(forecast.expected_return_comparison) as ExpectedReturnComparison;
  for (const model of [comparison.assets.historical, comparison.assets.forecast]) {
    model.signal.asset_ids = Array.from({ length: 500 }, (_, i) => `S${i.toString().padStart(3, "0")}`);
    model.signal.expected_returns = Array.from({ length: 500 }, () => .1);
  }
  render(<ReturnComparison comparison={comparison} />);
  expect(screen.getByText(/Allocation calculated with/)).toHaveTextContent("Simple forecast");
  expect(screen.getByText(/Both columns evaluate the same portfolio weights/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Asset estimates and estimator diagnostics"));
  expect(screen.getByText(/Effective sample size/)).toHaveTextContent("63 trading observations");
  const assets = within(screen.getByRole("region", { name: "Asset expected returns" }));
  expect(assets.getAllByRole("row")).toHaveLength(26);
  expect(assets.getByText("S000")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Next assets" }));
  expect(assets.queryByText("S000")).not.toBeInTheDocument();
  expect(assets.getByText("S025")).toBeInTheDocument();
  expect(screen.getByText("Page 2 of 21")).toBeInTheDocument();
});

it("retains old provenance while stale and recalculates only on submission", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(json(historical)).mockResolvedValueOnce(json(forecast));
  render(<PortfolioAnalysisWorkspace />);
  expect(screen.getByLabelText("Estimator")).toHaveValue("historical_mean");
  fireEvent.click(screen.getByRole("button", { name: "Compare alternatives" }));
  await screen.findByRole("heading", { name: "Historical vs forecast expected returns" });
  fireEvent.change(screen.getByLabelText("Estimator"), { target: { value: "simple_forecast" } });
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/Recommendations and simulations are stale/)).toBeInTheDocument();
  expect(screen.getByText(/Allocation calculated with/)).toHaveTextContent("Historical mean");
  expect(screen.getByRole("button", { name: "Explore uncertainty" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Compare alternatives" }));
  await waitFor(() => expect(screen.getByText(/Allocation calculated with/)).toHaveTextContent("Simple forecast"));
  expect(JSON.parse(String(fetch.mock.calls[1][1]?.body)).expected_return_estimator).toBe("simple_forecast");
  expect(screen.queryByText(/Recommendations and simulations are stale/)).not.toBeInTheDocument();
  const scenario = scenarioFromReport(forecast as unknown as FrontierReport, "10000", { horizon_years: 1, paths: 1000, seed: 42 });
  expect(scenario.portfolios.every((p) => p.metadata.return_estimator === "simple_exponential_forecast")).toBe(true);
});

it("ignores a superseded manual estimator response", async () => {
  let resolve!: (value: Response) => void;
  vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => new Promise((done) => { resolve = done; })).mockResolvedValueOnce(json(forecast));
  render(<PortfolioAnalysisWorkspace />);
  fireEvent.click(screen.getByRole("button", { name: "Compare alternatives" }));
  fireEvent.change(screen.getByLabelText("Estimator"), { target: { value: "simple_forecast" } });
  fireEvent.click(screen.getByRole("button", { name: "Compare alternatives" }));
  await screen.findByRole("heading", { name: "Historical vs forecast expected returns" });
  await act(async () => resolve(json(historical)));
  expect(screen.getByText(/Allocation calculated with/)).toHaveTextContent("Simple forecast");
});

it("carries guided selection through submission and ignores the old poll", async () => {
  let resolve!: (value: Response) => void;
  const completed = structuredClone(guided);
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(json({ id: "old" }))
    .mockImplementationOnce(() => new Promise((done) => { resolve = done; }))
    .mockResolvedValueOnce(json({ id: "new" })).mockResolvedValueOnce(json(completed));
  render(<GuidedBuilder />);
  for (const name of ["Prioritize smaller fluctuations", "Somewhat comfortable", "Accept continued exposure despite possible further losses"]) fireEvent.click(screen.getByRole("radio", { name }));
  fireEvent.click(screen.getByRole("button", { name: "Continue to capital" }));
  fireEvent.change(screen.getByLabelText("Investable capital (USD)"), { target: { value: "10000" } });
  fireEvent.click(screen.getByRole("button", { name: "Get recommendation" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  fireEvent.click(screen.getByRole("button", { name: "Back to capital and review" }));
  fireEvent.change(screen.getByLabelText("Estimator"), { target: { value: "simple_forecast" } });
  await act(async () => resolve(json({ status: "failed", error: { message: "Old error" } })));
  expect(screen.queryByText("Old error")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Get recommendation" }));
  await screen.findByRole("heading", { name: "Explore the trade-off" });
  expect(JSON.parse(String(fetch.mock.calls[2][1]?.body)).expected_return_estimator).toBe("simple_forecast");
});
