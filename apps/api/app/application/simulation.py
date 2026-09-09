"""Simulation use case depends only on the engine contract, never market data or solvers."""

from app.application.errors import invalid_input
from app.domain.simulation import (
    SimulationEngine,
    SimulationNumericalError,
    SimulationRequest,
    SimulationResult,
)


class PortfolioSimulationService:
    def __init__(self, engine: SimulationEngine) -> None:
        self._engine = engine

    def simulate(self, request: SimulationRequest) -> SimulationResult:
        try:
            return self._engine.simulate(request)
        except SimulationNumericalError as exc:
            raise invalid_input(
                "SIMULATION_NUMERICAL_FAILURE",
                "These parameters cannot produce finite simulation results.",
            ) from exc
