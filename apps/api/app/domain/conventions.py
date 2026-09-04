"""Explicit financial calculation conventions."""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.errors import DomainValidationError
from app.domain.models import Currency


class PriceField(StrEnum):
    ADJUSTED_CLOSE = "adjusted_close"


class ReturnConvention(StrEnum):
    SIMPLE = "simple"


class ReturnFrequency(StrEnum):
    DAILY = "daily"


class MissingDataPolicy(StrEnum):
    NO_IMPUTATION = "no_imputation"


class AlignmentPolicy(StrEnum):
    TIMESTAMP_INTERSECTION = "timestamp_intersection"


@dataclass(frozen=True, slots=True)
class FinancialConventions:
    """Single source of truth for financial calculation assumptions."""

    base_currency: Currency = Currency.USD
    price_field: PriceField = PriceField.ADJUSTED_CLOSE
    return_convention: ReturnConvention = ReturnConvention.SIMPLE
    return_frequency: ReturnFrequency = ReturnFrequency.DAILY
    annualization_periods: int = 252
    missing_data_policy: MissingDataPolicy = MissingDataPolicy.NO_IMPUTATION
    alignment_policy: AlignmentPolicy = AlignmentPolicy.TIMESTAMP_INTERSECTION

    def __post_init__(self) -> None:
        enum_fields = (
            (self.base_currency, Currency, "base_currency"),
            (self.price_field, PriceField, "price_field"),
            (self.return_convention, ReturnConvention, "return_convention"),
            (self.return_frequency, ReturnFrequency, "return_frequency"),
            (self.missing_data_policy, MissingDataPolicy, "missing_data_policy"),
            (self.alignment_policy, AlignmentPolicy, "alignment_policy"),
        )
        for value, expected_type, field_name in enum_fields:
            if not isinstance(value, expected_type):
                raise DomainValidationError(f"{field_name} has an unsupported value")
        if (
            isinstance(self.annualization_periods, bool)
            or not isinstance(self.annualization_periods, int)
            or self.annualization_periods <= 0
        ):
            raise DomainValidationError("annualization_periods must be a positive integer")


DEFAULT_FINANCIAL_CONVENTIONS = FinancialConventions()
