import { NextResponse } from "next/server";

import { DEFAULT_API_BASE_URL } from "@/lib/api-health";

export async function POST(request: Request) {
  const endpoint = `${(process.env.API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "")}/api/v1/portfolios/frontier`;
  try {
    const response = await fetch(endpoint, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: await request.text(),
      cache: "no-store", signal: AbortSignal.timeout(30_000),
    });
    return new NextResponse(await response.text(), {
      status: response.status, headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ code: "API_UNAVAILABLE", message: "The frontier API could not be reached. Please try again." }, { status: 503 });
  }
}
