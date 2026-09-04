"""Errors raised by domain value objects and entities."""


class DomainValidationError(ValueError):
    """Raised when data violates a domain invariant."""
