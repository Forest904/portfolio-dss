import type { FrontierReport, ProfileName } from "../portfolio-frontier/types";

export type QuestionId = "trade_off" | "fluctuations" | "decline";
export type Answers = Record<QuestionId, ProfileName>;
export type GuidedReport = {
  preference: { answers: Answers; version: string; suggested_profile: ProfileName;
    determining_answers: QuestionId[]; explanation: string };
  capital: string; currency: "USD";
  alternatives: { profile: ProfileName; allocations: { asset_id: string; weight: number; amount: string }[] }[];
  model: { report: FrontierReport; model_hash: string;
    coverage: { total: number; eligible: number; excluded: { asset_id: string; reason: string }[];
      policy: string; minimum_fraction: number };
    price_sources: FrontierReport["price_provenance"][] };
  report_hash: string;
};
export type GuidedJob = { id: string; status: "queued" | "running" | "completed" | "failed";
  stage: string; report: GuidedReport | null; error: { code: string; message: string; retryable: boolean } | null };
