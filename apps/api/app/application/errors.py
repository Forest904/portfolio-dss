"""Typed errors produced by application use cases."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ApplicationError(Exception):
    code: str
    message: str
    status_code: int
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


def invalid_input(code: str, message: str, **details: Any) -> ApplicationError:
    return ApplicationError(code, message, 422, details)


def not_found(code: str, message: str, **details: Any) -> ApplicationError:
    return ApplicationError(code, message, 404, details)


def data_unavailable(message: str, **details: Any) -> ApplicationError:
    return ApplicationError("MARKET_DATA_UNAVAILABLE", message, 503, details)
