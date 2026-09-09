import type { FrontierReport } from "../portfolio-frontier/types";

export type Settings = { horizon_years: number; paths: number; seed: number };
export type Metrics = { mean: number; standard_deviation: number; percentiles: number[] };
export type PortfolioSimulation = {
  id: string; terminal_value: Metrics; terminal_return: Metrics; probability_of_loss: number;
  fan: { month: number; percentiles: number[] }[]; histogram_counts: number[];
};
export type SimulationReport = {
  scenario: ReturnType<typeof scenarioFromReport>;
  assumptions: { model_version: string; rng_version: string; percentile_levels: number[]; statements: string[] };
  numerical_environment: string; portfolios: PortfolioSimulation[]; histogram_edges: number[];
  input_fingerprint: string; result_hash: string;
};

export function scenarioFromReport(report: FrontierReport, capital: string, configuration: Settings) {
  const portfolios = [
    ...report.frontier.profiles.map((profile) => ({ id: profile.name,
      metrics: report.frontier.points.find((point) => point.id === profile.point_id)!.metrics })),
    ...report.references,
  ].map((portfolio) => {
    const benchmark = portfolio.id === "sp500_proxy";
    const mean = benchmark ? report.benchmark_expected_return_model : report.expected_return_model;
    const risk = benchmark ? report.benchmark_risk_model : report.risk_model;
    if ([risk].some((m) => m.estimation_start !== mean.estimation_start || m.estimation_end !== mean.estimation_end ||
      m.observations !== mean.observations || m.frequency !== mean.frequency || m.return_convention !== mean.return_convention ||
      m.annualization_periods !== mean.annualization_periods)) throw new Error("The estimation conventions do not match.");
    return { id: portfolio.id, annual_mean: portfolio.metrics.expected_return, annual_variance: portfolio.metrics.variance,
      metadata: { estimation_start: mean.estimation_start, estimation_end: mean.estimation_end, observations: mean.observations,
        return_estimator: mean.estimator_name, risk_estimator: risk.estimator_name, currency: report.conventions.base_currency,
        price_field: report.conventions.price_field, return_convention: mean.return_convention, frequency: mean.frequency,
        annualization_periods: mean.annualization_periods } };
  });
  return { portfolios, initial_capital: Number(capital), source_report_hash: report.report_hash, configuration };
}
