import { describe, expect, it, vi } from "vitest";

import { checkApiHealth } from "./api-health";

describe("checkApiHealth", () => {
  it("accepts the exact healthy API contract", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({ status: "ok", service: "portfolio-dss-api", version: "0.1.0" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(checkApiHealth({ baseUrl: "http://api.test/", fetchImpl })).resolves.toEqual({
      available: true,
      health: { status: "ok", service: "portfolio-dss-api", version: "0.1.0" },
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://api.test/health",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("reports a malformed response", async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ status: "maybe" }), { status: 200 }));

    await expect(checkApiHealth({ fetchImpl })).resolves.toEqual({
      available: false,
      reason: "API returned an unexpected health response.",
    });
  });

  it("reports an unsuccessful HTTP response", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 503 }));

    await expect(checkApiHealth({ fetchImpl })).resolves.toEqual({
      available: false,
      reason: "API returned HTTP 503.",
    });
  });

  it("reports unreachable and timed-out requests", async () => {
    const unreachable = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("connection refused"));
    const timedOut = vi.fn<typeof fetch>().mockRejectedValue(new DOMException("timed out", "AbortError"));

    await expect(checkApiHealth({ fetchImpl: unreachable })).resolves.toEqual({
      available: false,
      reason: "API could not be reached.",
    });
    await expect(checkApiHealth({ fetchImpl: timedOut, timeoutMs: 1 })).resolves.toEqual({
      available: false,
      reason: "API could not be reached.",
    });
  });
});
