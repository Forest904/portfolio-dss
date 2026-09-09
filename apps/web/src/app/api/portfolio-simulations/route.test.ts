import { afterEach, expect, it, vi } from "vitest";

import { POST } from "./route";

afterEach(() => vi.restoreAllMocks());

it("forwards the request and preserves structured backend errors", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ code: "SIMULATION_NUMERICAL_FAILURE" }), { status: 422 }));
  const result = await POST(new Request("http://localhost/api/portfolio-simulations", { method: "POST", body: '{"positions":[]}' }));
  expect(result.status).toBe(422);
  expect(await result.json()).toEqual({ code: "SIMULATION_NUMERICAL_FAILURE" });
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/v1/portfolios/simulations"), expect.objectContaining({ body: '{"positions":[]}', cache: "no-store" }));
});

it("reports an unavailable backend", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("timeout"));
  const result = await POST(new Request("http://localhost/api/portfolio-simulations", { method: "POST", body: "{}" }));
  expect(result.status).toBe(503);
  expect((await result.json()).code).toBe("API_UNAVAILABLE");
});
