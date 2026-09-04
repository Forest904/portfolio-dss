import { NextResponse } from "next/server";

import { DEFAULT_API_BASE_URL } from "@/lib/api-health";

export async function POST(request: Request) {
  const endpoint = `${(process.env.API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "")}/api/v1/portfolios/analyze`;
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await request.text(),
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json(
      { code: "API_UNAVAILABLE", message: "The analysis API could not be reached." },
      { status: 503 },
    );
  }
}
