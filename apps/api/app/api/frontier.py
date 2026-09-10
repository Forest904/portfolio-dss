"""HTTP boundary for efficient-frontier reports."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request
from pydantic import Field

from app.api.schemas import (
    ApiModel,
    ErrorResponse,
    HistoryRequest,
    OptimizationConstraintsRequest,
    PositionRequest,
)
from app.application.estimators import EstimatorId, ExpectedReturnComparison
from app.application.frontier import DecisionFact, PortfolioFrontierService, ReferencePortfolio
from app.domain.analysis import AnalysisWindow
from app.domain.conventions import FinancialConventions
from app.domain.frontier import FrontierResult, ProfileConfiguration
from app.domain.market_data import DataProvenance
from app.domain.optimization import ExpectedReturnSignal, OptimizationConstraints, RiskEstimate

router = APIRouter()


class PortfolioFrontierRequest(ApiModel):
    expected_return_estimator: EstimatorId = "historical_mean"
    positions: list[PositionRequest] = Field(min_length=1)
    history: HistoryRequest | None = None
    constraints: OptimizationConstraintsRequest | None = None


class PortfolioFrontierResponse(ApiModel):
    expected_return_comparison: ExpectedReturnComparison | None = None
    window: AnalysisWindow
    frontier: FrontierResult
    references: tuple[ReferencePortfolio, ...]
    facts: tuple[DecisionFact, ...]
    expected_return_model: ExpectedReturnSignal
    risk_model: RiskEstimate
    benchmark_expected_return_model: ExpectedReturnSignal
    benchmark_risk_model: RiskEstimate
    constraints: OptimizationConstraints
    profile_configuration: ProfileConfiguration
    conventions: FinancialConventions
    universe_as_of: date
    universe_provenance: DataProvenance
    price_provenance: DataProvenance
    assumptions: tuple[str, ...]
    diagnostics: tuple[str, ...]
    report_hash: str
    holdings_capital: Decimal | None = None


@router.post(
    "/api/v1/portfolios/frontier",
    response_model=PortfolioFrontierResponse,
    responses={
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    tags=["portfolios"],
)
def generate_frontier(
    payload: PortfolioFrontierRequest, request: Request
) -> PortfolioFrontierResponse:
    service: PortfolioFrontierService = request.app.state.frontier_service
    report = service.generate(
        [(position.ticker, position.quantity) for position in payload.positions],
        max_weight=payload.constraints.max_weight if payload.constraints else None,
        expected_return_estimator=payload.expected_return_estimator,
        start=payload.history.start if payload.history else None,
        end=payload.history.end if payload.history else None,
    )
    return PortfolioFrontierResponse.model_validate(report, from_attributes=True)
