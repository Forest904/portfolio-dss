"""Schemas owned by the HTTP boundary."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.application.estimators import EstimatorId, ExpectedReturnComparison


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class HealthResponse(ApiModel):
    status: Literal["ok"]
    service: Literal["portfolio-dss-api"]
    version: str


class ErrorResponse(ApiModel):
    code: str
    message: str
    details: dict[str, Any]


class PositionRequest(ApiModel):
    ticker: str = Field(min_length=1)
    quantity: Decimal


class PortfolioValuationRequest(ApiModel):
    positions: list[PositionRequest] = Field(min_length=1)
    as_of: date | None = None


class HistoryRequest(ApiModel):
    start: date | None = None
    end: date | None = None


class PortfolioAnalysisRequest(ApiModel):
    positions: list[PositionRequest] = Field(min_length=1)
    history: HistoryRequest | None = None


class OptimizationConstraintsRequest(ApiModel):
    max_weight: float | None = Field(default=None, gt=0.0, le=1.0)


class PortfolioOptimizationRequest(ApiModel):
    positions: list[PositionRequest] = Field(min_length=1)
    risk_aversion: float = Field(ge=0.0)
    history: HistoryRequest | None = None
    constraints: OptimizationConstraintsRequest | None = None
    expected_return_estimator: EstimatorId = "historical_mean"


class ProvenanceResponse(ApiModel):
    provider: str
    retrieved_at: datetime
    content_hash: str
    stale_fallback: bool


class MoneyResponse(ApiModel):
    amount: Decimal
    currency: Literal["USD"]


class ValuationPositionResponse(ApiModel):
    ticker: str
    quantity: Decimal
    unit_price: MoneyResponse
    market_value: MoneyResponse
    weight: Decimal


class UniverseReferenceResponse(ApiModel):
    id: Literal["sp500"]
    as_of: date
    provenance: ProvenanceResponse


class PortfolioValuationResponse(ApiModel):
    requested_as_of: date | None
    valued_on: date
    total_market_value: MoneyResponse
    positions: list[ValuationPositionResponse]
    universe: UniverseReferenceResponse
    price_data: ProvenanceResponse
    snapshot_hash: str
    assumptions: list[str]


class BenchmarkResponse(ApiModel):
    asset_id: str
    name: str


class AssetResponse(ApiModel):
    ticker: str
    name: str
    exchange: str
    currency: Literal["USD"]
    sector: str
    industry: str | None


class UniverseResponse(ApiModel):
    id: Literal["sp500"]
    name: str
    as_of: date
    benchmark: BenchmarkResponse
    assets: list[AssetResponse]
    provenance: ProvenanceResponse
    assumptions: list[str]


class AnalysisValuationPositionResponse(ValuationPositionResponse):
    sector: str


class AnalysisValuationResponse(ApiModel):
    valued_on: date
    total_market_value: MoneyResponse
    positions: list[AnalysisValuationPositionResponse]


class ExcludedObservationResponse(ApiModel):
    asset_id: str
    count: int


class AnalysisWindowResponse(ApiModel):
    requested_start: date
    requested_end: date
    effective_start: date
    effective_end: date
    aligned_price_observations: int
    return_observations: int
    excluded_observations: list[ExcludedObservationResponse]


class ComparatorSeriesValueResponse(ApiModel):
    daily_return: float | None
    cumulative_return: float


class AnalysisSeriesPointResponse(ApiModel):
    date: date
    current: ComparatorSeriesValueResponse
    equal_weight: ComparatorSeriesValueResponse
    sp500_proxy: ComparatorSeriesValueResponse


class PerformanceSummaryResponse(ApiModel):
    total_return: float
    annualized_return: float
    annualized_volatility: float


class PerformanceComparisonResponse(ApiModel):
    current: PerformanceSummaryResponse
    equal_weight: PerformanceSummaryResponse
    sp500_proxy: PerformanceSummaryResponse
    current_vs_sp500_annualized_return: float
    current_vs_sp500_annualized_volatility: float
    equal_weight_vs_sp500_annualized_return: float
    equal_weight_vs_sp500_annualized_volatility: float


class LabelledMatrixResponse(ApiModel):
    asset_ids: list[str]
    values: list[list[float | None]]
    frequency: Literal["daily"]
    annualization_periods: int | None
    estimator: str


class ConcentrationComponentResponse(ApiModel):
    id: str
    weight: float


class ConcentrationSummaryResponse(ApiModel):
    components: list[ConcentrationComponentResponse]
    largest_id: str
    largest_weight: float
    top_three_weight: float
    hhi: float
    effective_count: float


class AnalysisConcentrationResponse(ApiModel):
    assets: ConcentrationSummaryResponse
    sectors: ConcentrationSummaryResponse


class AnalysisProvenanceResponse(ApiModel):
    universe: UniverseReferenceResponse
    price_data: ProvenanceResponse


class PortfolioAnalysisResponse(ApiModel):
    valuation: AnalysisValuationResponse
    window: AnalysisWindowResponse
    series: list[AnalysisSeriesPointResponse]
    performance: PerformanceComparisonResponse
    covariance: LabelledMatrixResponse
    correlation: LabelledMatrixResponse
    concentration: AnalysisConcentrationResponse
    provenance: AnalysisProvenanceResponse
    assumptions: list[str]
    diagnostics: list[str]
    analysis_hash: str


class AllocationComparisonResponse(ApiModel):
    ticker: str
    current_weight: float
    recommended_weight: float
    weight_change: float


class PortfolioMetricsResponse(ApiModel):
    expected_return: float
    variance: float
    volatility: float
    objective_value: float


class OptimizationComparisonResponse(ApiModel):
    current: PortfolioMetricsResponse
    recommended: PortfolioMetricsResponse
    expected_return_change: float
    variance_change: float
    volatility_change: float
    objective_change: float


class ExpectedReturnModelResponse(ApiModel):
    estimator: str
    asset_ids: list[str]
    annualized_expected_returns: list[float]
    frequency: Literal["daily"]
    return_convention: Literal["simple"]
    annualization_periods: int
    estimation_start: date
    estimation_end: date
    observations: int


class RiskModelResponse(ApiModel):
    estimator: str
    asset_ids: list[str]
    annualized_covariance: list[list[float]]
    frequency: Literal["daily"]
    return_convention: Literal["simple"]
    annualization_periods: int
    estimation_start: date
    estimation_end: date
    observations: int
    missing_data_policy: Literal["no_imputation"]


class OptimizationConfigurationResponse(ApiModel):
    risk_aversion: float
    max_weight: float | None


class SolverDiagnosticsResponse(ApiModel):
    solver: str
    success: bool
    status_code: int
    message: str
    iterations: int
    budget_residual: float
    minimum_weight: float
    max_weight_violation: float
    binding_asset_ids: list[str]


class PortfolioOptimizationResponse(ApiModel):
    expected_return_comparison: ExpectedReturnComparison
    window: AnalysisWindowResponse
    allocations: list[AllocationComparisonResponse]
    comparison: OptimizationComparisonResponse
    expected_return_model: ExpectedReturnModelResponse
    risk_model: RiskModelResponse
    configuration: OptimizationConfigurationResponse
    solver: SolverDiagnosticsResponse
    provenance: AnalysisProvenanceResponse
    assumptions: list[str]
    diagnostics: list[str]
    optimization_hash: str
