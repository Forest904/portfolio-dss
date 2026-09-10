export type ProfileName = "conservative" | "moderate" | "aggressive";
export type EstimatedMetrics = { expected_return: number; variance: number; volatility: number };
export type Weights = { asset_ids: string[]; weights: number[] };
export type SolverDiagnostics = {
  solver_name: string; success: boolean; status_code: number; message: string; iterations: number;
  budget_residual: number; minimum_weight: number; max_weight_violation: number; binding_asset_ids: string[];
};
export type FrontierPoint = {
  id: string; target_return: number; weights: Weights; metrics: EstimatedMetrics; solver: SolverDiagnostics;
};
export type ProfileReference = { name: ProfileName; fraction: number; target_return: number; point_id: string };
export type ReferencePortfolio = {
  id: "current" | "equal_weight" | "sp500_proxy"; weights: Weights; metrics: EstimatedMetrics;
  constraint_status: "valid" | "exceeds_max_weight" | "outside_investable_universe";
};
export type DecisionFact = {
  id: string; profile: ProfileName;
  kind: "expected_return_change" | "volatility_change" | "allocation_change" | "largest_holding" |
    "concentration" | "concentration_change" | "binding_cap" | "asset_expected_return" |
    "risk_contribution" | "risk_contribution_change" | "equivalent_profile";
  subject: string; comparison: string | null; value: number;
  unit: "percentage_points" | "weight_fraction" | "annual_fraction" | "hhi" | "flag";
};
export type DecisionReason = {
  id: string; category: "trade_off" | "allocation" | "diversification" | "constraint" | "model";
  headline: string; detail: string; evidence_fact_ids: string[];
};
export type DecisionExplanationSet = {
  profile: ProfileName; baseline: "current" | "equal_weight"; rule_version: string;
  summary: string; reasons: DecisionReason[];
};
type ModelMetadata = {
  asset_ids: string[]; frequency: "daily"; return_convention: "simple"; annualization_periods: number;
  estimation_start: string; estimation_end: string; observations: number; estimator_name: string; diagnostics: string[];
};
export type ReturnModel = ModelMetadata & { expected_returns: number[] };
type RiskModel = ModelMetadata & { covariance_matrix: number[][]; missing_data_policy: "no_imputation" };
type Provenance = { provider: string; retrieved_at: string; content_hash: string; stale_fallback: boolean };
export type FrontierReport = {
  expected_return_comparison?: import("../expected-returns/types").ExpectedReturnComparison | null;
  holdings_capital: string | null;
  window: { requested_start: string; requested_end: string; effective_start: string; effective_end: string;
    aligned_price_observations: number; return_observations: number; excluded_observations: [string, number][] };
  frontier: { points: FrontierPoint[]; profiles: ProfileReference[]; diagnostics: string[] };
  references: ReferencePortfolio[]; facts: DecisionFact[]; explanations: DecisionExplanationSet[];
  expected_return_model: ReturnModel; risk_model: RiskModel;
  benchmark_expected_return_model: ReturnModel; benchmark_risk_model: RiskModel;
  constraints: { max_weight: number | null };
  profile_configuration: { fractions: [number, number, number]; version: string };
  conventions: { base_currency: "USD"; price_field: "adjusted_close"; return_convention: "simple";
    return_frequency: "daily"; annualization_periods: number; missing_data_policy: "no_imputation";
    alignment_policy: "timestamp_intersection" };
  universe_as_of: string; universe_provenance: Provenance; price_provenance: Provenance;
  assumptions: string[]; diagnostics: string[]; report_hash: string;
};
