"""Errors raised by domain value objects and entities."""


class DomainValidationError(ValueError):
    """Raised when data violates a domain invariant."""


class MarketDataValidationError(DomainValidationError):
    """Raised when market data cannot safely enter a calculation."""


class ExternalDataUnavailableError(RuntimeError):
    """Raised by an adapter when an external source and usable cache are unavailable."""
