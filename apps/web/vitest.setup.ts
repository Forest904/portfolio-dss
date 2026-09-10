import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, vi } from "vitest";

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation((...values: unknown[]) => {
    throw new Error(`Unexpected console.error: ${values.map(String).join(" ")}`);
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
