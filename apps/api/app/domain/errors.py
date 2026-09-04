"""Errors raised by domain value objects and entities."""


class DomainValidationError(ValueError):
    """Raised when data violates a domain invariant."""


class MarketDataValidationError(DomainValidationError):
    """Raised when market data cannot safely enter a calculation."""


class ExternalDataUnavailableError(RuntimeError):
    """Raised by an adapter when an external source and usable cache are unavailable."""


class OptimizationSolverError(RuntimeError):
    """Raised when a valid optimization problem does not produce a valid solution."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}
