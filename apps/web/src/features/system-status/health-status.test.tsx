import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HealthStatus } from "./health-status";

describe("HealthStatus", () => {
  it("keeps the connected state out of the primary interface", () => {
    render(
      <HealthStatus
        availability={{
          available: true,
          health: { status: "ok", service: "portfolio-dss-api", version: "0.1.0" },
        }}
      />,
    );

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.queryByText(/API connected/i)).not.toBeInTheDocument();
  });

  it("renders the unavailable state while keeping guidance visible", () => {
    render(
      <HealthStatus availability={{ available: false, reason: "API could not be reached." }} />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("API unavailable");
    expect(screen.getByText(/start the API and refresh/i)).toBeInTheDocument();
  });
});
