"""FastAPI application composition root."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.frontier import router as frontier_router
from app.api.guided import router as guided_router
from app.api.router import router
from app.application import (
    ApplicationError,
    PortfolioAnalysisService,
    PortfolioOptimizationService,
    PortfolioValuationService,
)
from app.application.frontier import PortfolioFrontierService
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
from app.domain.frontier import EfficientFrontierGenerator
from app.infrastructure import (
    ScipyMeanVarianceOptimizer,
    SQLiteCache,
    WikipediaSP500Provider,
    YahooFinanceMarketDataProvider,
)
from app.infrastructure.frontier import ScipyEfficientFrontierGenerator
from app.infrastructure.guided_jobs import (
    ProcessGuidedJobs,
    ProductionGuidedFactory,
    SQLiteGuidedRepository,
)


def create_app(
    *,
    settings: Settings | None = None,
    universe_provider: CurrentUniverseProvider | None = None,
    market_data_provider: MarketDataProvider | None = None,
    expected_return_estimator: ExpectedReturnEstimator | None = None,
    risk_estimator: RiskEstimator | None = None,
    portfolio_optimizer: PortfolioOptimizer | None = None,
    frontier_generator: EfficientFrontierGenerator | None = None,
    clock: Callable[[], datetime] | None = None,
    guided_jobs: ProcessGuidedJobs | None = None,
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
    jobs = guided_jobs or ProcessGuidedJobs(
        SQLiteGuidedRepository(runtime.cache_path.with_name("guided_jobs.sqlite3")),
        ProductionGuidedFactory(runtime),
        lambda: repr(runtime.frontier_profiles) + datetime.now(UTC).date().isoformat(),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        jobs.start()
        try:
            yield
        finally:
            jobs.close()

    application = FastAPI(
        title=API_TITLE, description=API_DESCRIPTION, version=API_VERSION, lifespan=lifespan
    )
    application.state.guided_jobs = jobs
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

    application.state.frontier_service = PortfolioFrontierService(
        universe,
        prices,
        expected_return_estimator or HistoricalMeanEstimator(),
        risk_estimator or HistoricalSampleRiskEstimator(),
        frontier_generator or ScipyEfficientFrontierGenerator(),
        profiles=runtime.frontier_profiles,
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
                "details": {
                    "errors": jsonable_encoder(exc.errors(), custom_encoder={ValueError: str})
                },
            },
        )

    application.include_router(router)
    application.include_router(frontier_router)
    application.include_router(guided_router)
    return application


app = create_app()
