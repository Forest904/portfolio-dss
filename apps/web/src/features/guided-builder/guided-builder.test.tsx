import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import fixture from "./__fixtures__/completed.json";
import { GuidedBuilder, PortfolioWorkspace } from "./guided-builder";

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

function preferences() {
  fireEvent.click(screen.getByRole("radio", { name: "Prioritize smaller fluctuations" }));
  fireEvent.click(screen.getByRole("radio", { name: "Somewhat comfortable" }));
  fireEvent.click(screen.getByRole("radio", { name: "Accept continued exposure despite possible further losses" }));
  fireEvent.click(screen.getByRole("button", { name: "Continue to capital" }));
}
function submit() {
  preferences();
  fireEvent.change(screen.getByLabelText("Investable capital (USD)"), { target: { value: "1000.01" } });
  fireEvent.click(screen.getByRole("button", { name: "Get recommendation" }));
}

describe("Guided builder", () => {
  it("starts with the builder, no preselected answers, and keeps existing analysis accessible", () => {
    render(<PortfolioWorkspace />);
    expect(screen.getAllByRole("radio")).toHaveLength(9);
    screen.getAllByRole("radio").forEach((radio) => expect(radio).not.toBeChecked());
    fireEvent.click(screen.getByRole("button", { name: "Analyze existing holdings" }));
    expect(screen.getByLabelText("Ticker 1")).toBeInTheDocument();
  });

  it("preserves answers and capital when moving backward", () => {
    render(<GuidedBuilder />);
    preferences();
    expect(screen.getByLabelText("Investable capital (USD)")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Investable capital (USD)"), { target: { value: "123.45" } });
    fireEvent.click(screen.getByRole("button", { name: "Back to preferences" }));
    expect(screen.getByRole("radio", { name: "Prioritize smaller fluctuations" })).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Continue to capital" }));
    expect(screen.getByLabelText("Investable capital (USD)")).toHaveValue("123.45");
  });

  it("reaches a suggested recommendation and explores alternatives without a new request", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(json({ id: "fixture-job" }, 202)).mockResolvedValueOnce(json(fixture));
    render(<GuidedBuilder />);
    submit();
    await screen.findByRole("heading", { name: "Explore the trade-off" });
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ version: "guided-preferences-v1", capital: "1000.01", answers: { trade_off: "conservative", fluctuations: "moderate", decline: "aggressive" } });
    expect(screen.getByRole("radio", { name: /^Conservative/ })).toBeChecked();
    expect(screen.queryByText("Current weight")).not.toBeInTheDocument();
    expect(screen.getByText(/12 of 12 current constituent/)).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Amount (USD)" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /^Aggressive/ }));
    expect(screen.getByText(/Exploring the Aggressive alternative/)).toBeInTheDocument();
    expect(within(screen.getByRole("table", { name: "Allocation comparison" })).getByText("Aggressive weight")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("shows failures and allows retry", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(json({ id: "first" }, 202))
      .mockResolvedValueOnce(json({ status: "failed", stage: "failed", error: { message: "Insufficient stock coverage." } }))
      .mockResolvedValueOnce(json({ id: "second" }, 202)).mockResolvedValueOnce(json(fixture));
    render(<GuidedBuilder />);
    submit();
    expect(await screen.findByRole("alert")).toHaveTextContent("Insufficient stock coverage.");
    fireEvent.click(screen.getByRole("button", { name: "Retry calculation" }));
    await screen.findByRole("heading", { name: "Explore the trade-off" });
  });

  it("ignores a late result after changed capital", async () => {
    let resolve!: (response: Response) => void;
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(json({ id: "first" }, 202))
      .mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    render(<GuidedBuilder />);
    submit();
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "Back to capital and review" }));
    fireEvent.change(screen.getByLabelText("Investable capital (USD)"), { target: { value: "200" } });
    await act(async () => resolve(json(fixture)));
    expect(screen.queryByRole("heading", { name: "Explore the trade-off" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Investable capital (USD)")).toHaveValue("200");
  });

  it("polls after two seconds and stops when the journey is inactive", async () => {
    vi.useFakeTimers();
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(json({ id: "first" }, 202))
      .mockImplementation(async () => json({ id: "first", status: "running", stage: "loading_prices" }));
    const { rerender } = render(<GuidedBuilder />);
    submit();
    await act(async () => {});
    expect(fetch).toHaveBeenCalledTimes(2);
    await act(async () => vi.advanceTimersByTime(1999));
    expect(fetch).toHaveBeenCalledTimes(2);
    await act(async () => vi.advanceTimersByTime(1));
    expect(fetch).toHaveBeenCalledTimes(3);
    rerender(<GuidedBuilder active={false} />);
    await act(async () => vi.advanceTimersByTime(10000));
    expect(fetch).toHaveBeenCalledTimes(3);
  });
});
