import pytest

from app.domain import (
    DEFAULT_FINANCIAL_CONVENTIONS,
    AlignmentPolicy,
    Currency,
    DomainValidationError,
    FinancialConventions,
    MissingDataPolicy,
    PriceField,
    ReturnConvention,
    ReturnFrequency,
)


def test_default_financial_conventions_are_explicit() -> None:
    assert (
        FinancialConventions(
            base_currency=Currency.USD,
            price_field=PriceField.ADJUSTED_CLOSE,
            return_convention=ReturnConvention.SIMPLE,
            return_frequency=ReturnFrequency.DAILY,
            annualization_periods=252,
            missing_data_policy=MissingDataPolicy.NO_IMPUTATION,
            alignment_policy=AlignmentPolicy.TIMESTAMP_INTERSECTION,
        )
        == DEFAULT_FINANCIAL_CONVENTIONS
    )


@pytest.mark.parametrize("periods", [0, -1, True, 252.0])
def test_annualization_periods_must_be_a_positive_integer(periods: object) -> None:
    with pytest.raises(DomainValidationError):
        FinancialConventions(annualization_periods=periods)  # type: ignore[arg-type]


def test_unsupported_currency_is_rejected() -> None:
    with pytest.raises(DomainValidationError):
        FinancialConventions(base_currency="EUR")  # type: ignore[arg-type]
