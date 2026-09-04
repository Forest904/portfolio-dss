"""Operational and versioned financial API routes."""

from fastapi import APIRouter, Request

from app.api.schemas import (
    AssetResponse,
    BenchmarkResponse,
    ErrorResponse,
    HealthResponse,
    MoneyResponse,
    PortfolioValuationRequest,
    PortfolioValuationResponse,
    ProvenanceResponse,
    UniverseReferenceResponse,
    UniverseResponse,
    ValuationPositionResponse,
)
from app.application import PortfolioValuationService, normalize_ticker
from app.application.errors import data_unavailable, not_found
from app.core.config import API_VERSION, SERVICE_NAME
from app.domain import CurrentUniverseProvider, ExternalDataUnavailableError

router = APIRouter()


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
