"""FastAPI application composition root."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.router import router
from app.application import (
    ApplicationError,
    PortfolioAnalysisService,
    PortfolioOptimizationService,
    PortfolioValuationService,
)
from app.core.config import API_DESCRIPTION, API_TITLE, API_VERSION, Settings, load_settings
from app.domain import (
    CurrentUniverseProvider,
    ExpectedReturnEstimator,
    HistoricalMeanEstimator,
    HistoricalSampleRiskEstimator,
    MarketDataProvider,
    PortfolioOptimizer,
    RiskEstimator,
)
from app.infrastructure import (
    ScipyMeanVarianceOptimizer,
    SQLiteCache,
    WikipediaSP500Provider,
    YahooFinanceMarketDataProvider,
)


def create_app(
    *,
    settings: Settings | None = None,
    universe_provider: CurrentUniverseProvider | None = None,
    market_data_provider: MarketDataProvider | None = None,
    expected_return_estimator: ExpectedReturnEstimator | None = None,
    risk_estimator: RiskEstimator | None = None,
    portfolio_optimizer: PortfolioOptimizer | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    runtime = settings or load_settings()
    cache = SQLiteCache(runtime.cache_path)
    universe = universe_provider or WikipediaSP500Provider(
        cache,
        timeout_seconds=runtime.provider_timeout_seconds,
        refresh_ttl=timedelta(hours=runtime.universe_cache_ttl_hours),
        stale_fallback_limit=timedelta(days=runtime.stale_fallback_days),
        clock=clock,
    )
    prices = market_data_provider or YahooFinanceMarketDataProvider(
        cache,
        timeout_seconds=runtime.provider_timeout_seconds,
        refresh_ttl=timedelta(hours=runtime.price_cache_ttl_hours),
        stale_fallback_limit=timedelta(days=runtime.stale_fallback_days),
        clock=clock,
    )
    application = FastAPI(title=API_TITLE, description=API_DESCRIPTION, version=API_VERSION)
    application.state.universe_provider = universe
    application.state.valuation_service = PortfolioValuationService(
        universe,
        prices,
        clock=clock,
        maximum_staleness_days=runtime.stale_fallback_days,
        maximum_consecutive_missing=runtime.maximum_consecutive_missing,
    )
    application.state.analysis_service = PortfolioAnalysisService(
        universe,
        prices,
        clock=clock,
        maximum_consecutive_missing=runtime.maximum_consecutive_missing,
    )
    application.state.optimization_service = PortfolioOptimizationService(
        universe,
        prices,
        expected_return_estimator or HistoricalMeanEstimator(),
        risk_estimator or HistoricalSampleRiskEstimator(),
        portfolio_optimizer or ScipyMeanVarianceOptimizer(),
        clock=clock,
        maximum_consecutive_missing=runtime.maximum_consecutive_missing,
    )

    @application.exception_handler(ApplicationError)
    async def handle_application_error(_: Request, exc: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "details": exc.details},
        )

    @application.exception_handler(RequestValidationError)
    async def handle_request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "The request payload is invalid.",
                "details": {"errors": exc.errors()},
            },
        )

    application.include_router(router)
    return application


app = create_app()
