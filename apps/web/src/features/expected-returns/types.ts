import type { ReturnModel } from "../portfolio-frontier/types";

export type EstimatorId = "historical_mean" | "simple_forecast";
export type ComparedModel = {
  signal: ReturnModel;
  metadata: {
    model_id: EstimatorId; version: string; weighting_method: string;
    half_life_observations: number | null; effective_sample_size: number;
    latest_observation_weight: number; estimation_start: string; estimation_end: string;
    observations: number;
  };
};
export type ModelPair = { historical: ComparedModel; forecast: ComparedModel };
export type ExpectedReturnComparison = {
  selected_estimator: EstimatorId; assets: ModelPair; benchmark: ModelPair | null; version: string;
  portfolios: { id: string; historical_expected_return: number; forecast_expected_return: number; difference: number }[];
};
