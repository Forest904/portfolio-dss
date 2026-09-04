export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export type ApiHealth = {
  status: "ok";
  service: "portfolio-dss-api";
  version: string;
};

export type ApiAvailability =
  | { available: true; health: ApiHealth }
  | { available: false; reason: string };

type HealthCheckOptions = {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
};

function isApiHealth(value: unknown): value is ApiHealth {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    candidate.status === "ok" &&
    candidate.service === "portfolio-dss-api" &&
    typeof candidate.version === "string" &&
    candidate.version.length > 0
  );
}

export async function checkApiHealth({
  baseUrl = process.env.API_BASE_URL ?? DEFAULT_API_BASE_URL,
  fetchImpl = fetch,
  timeoutMs = 1_500,
}: HealthCheckOptions = {}): Promise<ApiAvailability> {
  const endpoint = `${baseUrl.replace(/\/$/, "")}/health`;

  try {
    const response = await fetchImpl(endpoint, {
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!response.ok) {
      return { available: false, reason: `API returned HTTP ${response.status}.` };
    }

    const payload: unknown = await response.json();
    if (!isApiHealth(payload)) {
      return { available: false, reason: "API returned an unexpected health response." };
    }

    return { available: true, health: payload };
  } catch {
    return { available: false, reason: "API could not be reached." };
  }
}
