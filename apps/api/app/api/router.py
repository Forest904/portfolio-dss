"""Operational and versioned financial API routes."""

from fastapi import APIRouter, Request

from app.api.schemas import (
    AllocationComparisonResponse,
    AnalysisConcentrationResponse,
    AnalysisProvenanceResponse,
    AnalysisSeriesPointResponse,
    AnalysisValuationPositionResponse,
    AnalysisValuationResponse,
    AnalysisWindowResponse,
    AssetResponse,
    BenchmarkResponse,
    ComparatorSeriesValueResponse,
    ConcentrationSummaryResponse,
    ErrorResponse,
    ExcludedObservationResponse,
    ExpectedReturnModelResponse,
    HealthResponse,
    LabelledMatrixResponse,
    MoneyResponse,
    OptimizationComparisonResponse,
    OptimizationConfigurationResponse,
    PerformanceComparisonResponse,
    PerformanceSummaryResponse,
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
    PortfolioMetricsResponse,
    PortfolioOptimizationRequest,
    PortfolioOptimizationResponse,
    PortfolioValuationRequest,
    PortfolioValuationResponse,
    ProvenanceResponse,
    RiskModelResponse,
    SolverDiagnosticsResponse,
    UniverseReferenceResponse,
    UniverseResponse,
    ValuationPositionResponse,
)
from app.application import (
    PortfolioAnalysisService,
    PortfolioOptimizationService,
    PortfolioValuationService,
    normalize_ticker,
)
from app.application.errors import data_unavailable, not_found
from app.core.config import API_VERSION, SERVICE_NAME
from app.domain import (
    DEFAULT_FINANCIAL_CONVENTIONS,
    CurrentUniverseProvider,
    ExternalDataUnavailableError,
)

router = APIRouter()


def performance_response(value: object) -> PerformanceSummaryResponse:
    return PerformanceSummaryResponse.model_validate(value, from_attributes=True)


def concentration_response(value: object) -> ConcentrationSummaryResponse:
    result = ConcentrationSummaryResponse.model_validate(value, from_attributes=True)
    return result


def portfolio_metrics_response(value: object) -> PortfolioMetricsResponse:
    return PortfolioMetricsResponse.model_validate(value, from_attributes=True)


def provenance_response(value: object) -> ProvenanceResponse:
    return ProvenanceResponse.model_validate(value, from_attributes=True)


def universe_provider(request: Request) -> CurrentUniverseProvider:
    return request.app.state.universe_provider  # type: ignore[no-any-return]


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, version=API_VERSION)


@router.post(
    "/api/v1/portfolios/valuation",
    response_model=PortfolioValuationResponse,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["portfolios"],
)
def value_portfolio(
    payload: PortfolioValuationRequest, request: Request
) -> PortfolioValuationResponse:
    service: PortfolioValuationService = request.app.state.valuation_service
    snapshot = service.value(
        [(position.ticker, position.quantity) for position in payload.positions], payload.as_of
    )
    return PortfolioValuationResponse(
        requested_as_of=snapshot.requested_as_of,
        valued_on=snapshot.valued_on,
        total_market_value=MoneyResponse(amount=snapshot.total_market_value, currency="USD"),
        positions=[
            ValuationPositionResponse(
                ticker=line.ticker,
                quantity=line.quantity,
                unit_price=MoneyResponse(amount=line.unit_price, currency="USD"),
                market_value=MoneyResponse(amount=line.market_value, currency="USD"),
                weight=line.weight,
            )
            for line in snapshot.positions
        ],
        universe=UniverseReferenceResponse(
            id="sp500",
            as_of=snapshot.universe_as_of,
            provenance=provenance_response(snapshot.universe_provenance),
        ),
        price_data=provenance_response(snapshot.price_provenance),
        snapshot_hash=snapshot.snapshot_hash,
        assumptions=list(snapshot.assumptions),
    )


@router.post(
    "/api/v1/portfolios/analyze",
    response_model=PortfolioAnalysisResponse,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["portfolios"],
)
def analyze_portfolio(
    payload: PortfolioAnalysisRequest, request: Request
) -> PortfolioAnalysisResponse:
    service: PortfolioAnalysisService = request.app.state.analysis_service
    report = service.analyze(
        [(position.ticker, position.quantity) for position in payload.positions],
        start=payload.history.start if payload.history else None,
        end=payload.history.end if payload.history else None,
    )
    analytics = report.analytics
    return PortfolioAnalysisResponse(
        valuation=AnalysisValuationResponse(
            valued_on=report.valuation.valued_on,
            total_market_value=MoneyResponse(
                amount=report.valuation.total_market_value, currency="USD"
            ),
            positions=[
                AnalysisValuationPositionResponse(
                    ticker=line.ticker,
                    quantity=line.quantity,
                    unit_price=MoneyResponse(amount=line.unit_price, currency="USD"),
                    market_value=MoneyResponse(amount=line.market_value, currency="USD"),
                    weight=line.weight,
                    sector=line.sector,
                )
                for line in report.valuation.positions
            ],
        ),
        window=AnalysisWindowResponse(
            requested_start=report.window.requested_start,
            requested_end=report.window.requested_end,
            effective_start=report.window.effective_start,
            effective_end=report.window.effective_end,
            aligned_price_observations=report.window.aligned_price_observations,
            return_observations=report.window.return_observations,
            excluded_observations=[
                ExcludedObservationResponse(asset_id=asset_id, count=count)
                for asset_id, count in report.window.excluded_observations
            ],
        ),
        series=[
            AnalysisSeriesPointResponse(
                date=current.observed_on,
                current=ComparatorSeriesValueResponse(
                    daily_return=current.daily_return,
                    cumulative_return=current.cumulative_return,
                ),
                equal_weight=ComparatorSeriesValueResponse(
                    daily_return=equal_weight.daily_return,
                    cumulative_return=equal_weight.cumulative_return,
                ),
                sp500_proxy=ComparatorSeriesValueResponse(
                    daily_return=benchmark.daily_return,
                    cumulative_return=benchmark.cumulative_return,
                ),
            )
            for current, equal_weight, benchmark in zip(
                analytics.current_series,
                analytics.equal_weight_series,
                analytics.benchmark_series,
                strict=True,
            )
        ],
        performance=PerformanceComparisonResponse(
            current=performance_response(analytics.current_performance),
            equal_weight=performance_response(analytics.equal_weight_performance),
            sp500_proxy=performance_response(analytics.benchmark_performance),
            current_vs_sp500_annualized_return=(
                analytics.current_performance.annualized_return
                - analytics.benchmark_performance.annualized_return
            ),
            current_vs_sp500_annualized_volatility=(
                analytics.current_performance.annualized_volatility
                - analytics.benchmark_performance.annualized_volatility
            ),
            equal_weight_vs_sp500_annualized_return=(
                analytics.equal_weight_performance.annualized_return
                - analytics.benchmark_performance.annualized_return
            ),
            equal_weight_vs_sp500_annualized_volatility=(
                analytics.equal_weight_performance.annualized_volatility
                - analytics.benchmark_performance.annualized_volatility
            ),
        ),
        covariance=LabelledMatrixResponse(
            asset_ids=list(analytics.covariance.asset_ids),
            values=[list(row) for row in analytics.covariance.values],
            frequency="daily",
            annualization_periods=DEFAULT_FINANCIAL_CONVENTIONS.annualization_periods,
            estimator="sample_covariance",
        ),
        correlation=LabelledMatrixResponse(
            asset_ids=list(analytics.correlation.asset_ids),
            values=[list(row) for row in analytics.correlation.values],
            frequency="daily",
            annualization_periods=None,
            estimator="pearson_sample_correlation",
        ),
        concentration=AnalysisConcentrationResponse(
            assets=concentration_response(analytics.asset_concentration),
            sectors=concentration_response(analytics.sector_concentration),
        ),
        provenance=AnalysisProvenanceResponse(
            universe=UniverseReferenceResponse(
                id="sp500",
                as_of=report.universe_as_of,
                provenance=provenance_response(report.universe_provenance),
            ),
            price_data=provenance_response(report.price_provenance),
        ),
        assumptions=list(report.assumptions),
        diagnostics=list(report.diagnostics),
        analysis_hash=report.analysis_hash,
    )


@router.post(
    "/api/v1/portfolios/optimize",
    response_model=PortfolioOptimizationResponse,
    responses={
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    tags=["portfolios"],
)
def optimize_portfolio(
    payload: PortfolioOptimizationRequest, request: Request
) -> PortfolioOptimizationResponse:
    service: PortfolioOptimizationService = request.app.state.optimization_service
    report = service.optimize(
        [(position.ticker, position.quantity) for position in payload.positions],
        risk_aversion=payload.risk_aversion,
        expected_return_estimator=payload.expected_return_estimator,
        max_weight=payload.constraints.max_weight if payload.constraints else None,
        start=payload.history.start if payload.history else None,
        end=payload.history.end if payload.history else None,
    )
    current = report.current_metrics
    recommended = report.optimization.metrics
    signal = report.expected_returns
    risk = report.risk_estimate
    solver = report.optimization.solver
    return PortfolioOptimizationResponse(
        expected_return_comparison=report.expected_return_comparison,
        window=AnalysisWindowResponse(
            requested_start=report.window.requested_start,
            requested_end=report.window.requested_end,
            effective_start=report.window.effective_start,
            effective_end=report.window.effective_end,
            aligned_price_observations=report.window.aligned_price_observations,
            return_observations=report.window.return_observations,
            excluded_observations=[
                ExcludedObservationResponse(asset_id=asset_id, count=count)
                for asset_id, count in report.window.excluded_observations
            ],
        ),
        allocations=[
            AllocationComparisonResponse(
                ticker=item.asset_id,
                current_weight=item.current_weight,
                recommended_weight=item.recommended_weight,
                weight_change=item.weight_change,
            )
            for item in report.allocations
        ],
        comparison=OptimizationComparisonResponse(
            current=portfolio_metrics_response(current),
            recommended=portfolio_metrics_response(recommended),
            expected_return_change=recommended.expected_return - current.expected_return,
            variance_change=recommended.variance - current.variance,
            volatility_change=recommended.volatility - current.volatility,
            objective_change=recommended.objective_value - current.objective_value,
        ),
        expected_return_model=ExpectedReturnModelResponse(
            estimator=signal.estimator_name,
            asset_ids=list(signal.asset_ids),
            annualized_expected_returns=list(signal.expected_returns),
            frequency="daily",
            return_convention="simple",
            annualization_periods=signal.annualization_periods,
            estimation_start=signal.estimation_start,
            estimation_end=signal.estimation_end,
            observations=signal.observations,
        ),
        risk_model=RiskModelResponse(
            estimator=risk.estimator_name,
            asset_ids=list(risk.asset_ids),
            annualized_covariance=[list(row) for row in risk.covariance_matrix],
            frequency="daily",
            return_convention="simple",
            annualization_periods=risk.annualization_periods,
            estimation_start=risk.estimation_start,
            estimation_end=risk.estimation_end,
            observations=risk.observations,
            missing_data_policy="no_imputation",
        ),
        configuration=OptimizationConfigurationResponse(
            risk_aversion=report.risk_aversion, max_weight=report.max_weight
        ),
        solver=SolverDiagnosticsResponse(
            solver=solver.solver_name,
            success=solver.success,
            status_code=solver.status_code,
            message=solver.message,
            iterations=solver.iterations,
            budget_residual=solver.budget_residual,
            minimum_weight=solver.minimum_weight,
            max_weight_violation=solver.max_weight_violation,
            binding_asset_ids=list(solver.binding_asset_ids),
        ),
        provenance=AnalysisProvenanceResponse(
            universe=UniverseReferenceResponse(
                id="sp500",
                as_of=report.universe_as_of,
                provenance=provenance_response(report.universe_provenance),
            ),
            price_data=provenance_response(report.price_provenance),
        ),
        assumptions=list(report.assumptions),
        diagnostics=list(report.diagnostics),
        optimization_hash=report.optimization_hash,
    )


@router.get("/api/v1/universes/sp500", response_model=UniverseResponse, tags=["universes"])
def get_sp500(request: Request) -> UniverseResponse:
    try:
        snapshot = universe_provider(request).get_current_universe()
    except ExternalDataUnavailableError as exc:
        raise data_unavailable(str(exc), source="wikipedia") from exc
    return UniverseResponse(
        id="sp500",
        name=snapshot.universe.name,
        as_of=snapshot.universe.as_of_date,
        benchmark=BenchmarkResponse(
            asset_id=snapshot.universe.benchmark_asset_id,
            name=snapshot.universe.benchmark_name,
        ),
        assets=[
            AssetResponse.model_validate(asset, from_attributes=True) for asset in snapshot.assets
        ],
        provenance=provenance_response(snapshot.provenance),
        assumptions=[
            "This is a current constituent snapshot, not reconstructed historical membership.",
            "SPY is a separate total-return ETF benchmark proxy and is not a constituent.",
        ],
    )


@router.get(
    "/api/v1/assets/{ticker}",
    response_model=AssetResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["assets"],
)
def get_asset(ticker: str, request: Request) -> AssetResponse:
    normalized = normalize_ticker(ticker)
    try:
        snapshot = universe_provider(request).get_current_universe()
    except ExternalDataUnavailableError as exc:
        raise data_unavailable(str(exc), source="wikipedia") from exc
    asset = next((item for item in snapshot.assets if item.ticker == normalized), None)
    if asset is None:
        raise not_found(
            "ASSET_NOT_FOUND", "Ticker is not a current S&P 500 constituent.", ticker=normalized
        )
    return AssetResponse.model_validate(asset, from_attributes=True)
