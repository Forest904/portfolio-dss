"""Stateless HTTP boundary for explicitly supplied simulation scenarios."""

from fastapi import APIRouter, Request
from pydantic import field_validator

from app.api.schemas import ApiModel, ErrorResponse
from app.application.simulation import PortfolioSimulationService
from app.domain.simulation import SimulationRequest, SimulationResult

router = APIRouter()


class SimulationPayload(ApiModel):
    scenario: SimulationRequest

    @field_validator("scenario", mode="before")
    @classmethod
    def strict_numbers(cls, value: object) -> object:
        # Dataclass parsing otherwise coerces booleans and strings before domain validation.
        if isinstance(value, dict):
            configuration = value.get("configuration", {})
            if isinstance(configuration, dict) and any(
                type(v) is not int for v in configuration.values()
            ):
                raise ValueError("Simulation settings must be integers")
            capital = value.get("initial_capital")
            if type(capital) not in (int, float):
                raise ValueError("Capital must be numerical")
            portfolios = value.get("portfolios", [])
            if isinstance(portfolios, list):
                for portfolio in portfolios:
                    if isinstance(portfolio, dict):
                        if any(
                            type(portfolio.get(k)) not in (int, float)
                            for k in ("annual_mean", "annual_variance")
                        ):
                            raise ValueError("Portfolio parameters must be numerical")
                        metadata = portfolio.get("metadata", {})
                        if isinstance(metadata, dict) and any(
                            type(metadata.get(k, 252)) is not int
                            for k in ("observations", "annualization_periods")
                        ):
                            raise ValueError("Observation counts must be integers")
        return value


@router.post(
    "/api/v1/portfolios/simulations",
    response_model=SimulationResult,
    responses={422: {"model": ErrorResponse}},
    tags=["portfolios"],
)
def simulate(payload: SimulationPayload, request: Request) -> SimulationResult:
    service: PortfolioSimulationService = request.app.state.simulation_service
    return service.simulate(payload.scenario)
