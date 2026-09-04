export type Money = { amount: string; currency: "USD" };

export type PerformanceSummary = {
  total_return: number;
  annualized_return: number;
  annualized_volatility: number;
};

export type SeriesValue = { daily_return: number | null; cumulative_return: number };

export type AnalysisSeriesPoint = {
  date: string;
  current: SeriesValue;
  equal_weight: SeriesValue;
  sp500_proxy: SeriesValue;
};

export type ConcentrationSummary = {
  components: { id: string; weight: number }[];
  largest_id: string;
  largest_weight: number;
  top_three_weight: number;
  hhi: number;
  effective_count: number;
};

export type PortfolioAnalysis = {
  valuation: {
    valued_on: string;
    total_market_value: Money;
    positions: {
      ticker: string;
      quantity: string;
      unit_price: Money;
      market_value: Money;
      weight: string;
      sector: string;
    }[];
  };
  window: {
    requested_start: string;
    requested_end: string;
    effective_start: string;
    effective_end: string;
    aligned_price_observations: number;
    return_observations: number;
    excluded_observations: { asset_id: string; count: number }[];
  };
  series: AnalysisSeriesPoint[];
  performance: {
    current: PerformanceSummary;
    equal_weight: PerformanceSummary;
    sp500_proxy: PerformanceSummary;
    current_vs_sp500_annualized_return: number;
    current_vs_sp500_annualized_volatility: number;
    equal_weight_vs_sp500_annualized_return: number;
    equal_weight_vs_sp500_annualized_volatility: number;
  };
  covariance: { asset_ids: string[]; values: (number | null)[][]; estimator: string };
  correlation: { asset_ids: string[]; values: (number | null)[][]; estimator: string };
  concentration: { assets: ConcentrationSummary; sectors: ConcentrationSummary };
  provenance: {
    universe: { as_of: string; provenance: { provider: string; content_hash: string } };
    price_data: {
      provider: string;
      retrieved_at: string;
      content_hash: string;
      stale_fallback: boolean;
    };
  };
  assumptions: string[];
  diagnostics: string[];
  analysis_hash: string;
};

export type AnalysisError = { code: string; message: string; details?: Record<string, unknown> };
