import { afterEach, expect, it, vi } from "vitest";
import { POST } from "@/app/api/guided-recommendations/route";
import { GET } from "@/app/api/guided-recommendations/[id]/route";

afterEach(() => vi.restoreAllMocks());

it("forwards submission and status without caching", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response('{"id":"job"}', { status: 202 }))
    .mockResolvedValueOnce(new Response('{"code":"JOB_NOT_FOUND"}', { status: 404 }));
  expect((await POST(new Request("http://localhost", { method: "POST", body: '{"capital":"10"}' }))).status).toBe(202);
  expect(fetch.mock.calls[0][1]?.body).toBe('{"capital":"10"}');
  const response = await GET(new Request("http://localhost"), { params: Promise.resolve({ id: "job" }) });
  expect(response.status).toBe(404);
  expect(response.headers.get("Cache-Control")).toBe("no-store");
  expect(fetch.mock.calls[1][0]).toContain("/guided-recommendations/job");
});

it("handles a disconnected API", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
  const response = await GET(new Request("http://localhost"), { params: Promise.resolve({ id: "job" }) });
  expect(response.status).toBe(503);
  expect(await response.json()).toMatchObject({ code: "API_UNAVAILABLE" });
});
