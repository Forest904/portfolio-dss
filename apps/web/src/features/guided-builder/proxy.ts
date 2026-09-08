import { NextResponse } from "next/server";
import { DEFAULT_API_BASE_URL } from "@/lib/api-health";

export async function forwardGuided(path: string, init: RequestInit) {
  const base = (process.env.API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");
  try {
    const response = await fetch(`${base}/api/v1/guided-recommendations${path}`, { ...init, cache: "no-store", signal: AbortSignal.timeout(30_000) });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": response.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ code: "API_UNAVAILABLE", message: "The recommendation API could not be reached. Please try again." }, { status: 503 });
  }
}
