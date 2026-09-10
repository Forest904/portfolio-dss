from datetime import date

import pytest

from app.domain import (
    MissingDataPolicy,
    PortfolioWeights,
    ReturnConvention,
    ReturnFrequency,
    RiskEstimate,
    portfolio_risk_contributions,
)


def estimate(asset_ids: tuple[str, ...], covariance: tuple[tuple[float, ...], ...]) -> RiskEstimate:
    return RiskEstimate(
        asset_ids,
        covariance,
        ReturnFrequency.DAILY,
        ReturnConvention.SIMPLE,
        252,
        date(2025, 1, 1),
        date(2025, 12, 31),
        252,
        MissingDataPolicy.NO_IMPUTATION,
        "fixture",
    )


def test_risk_contributions_match_hand_calculation_and_sum() -> None:
    result = portfolio_risk_contributions(
        PortfolioWeights(("A", "B"), (0.25, 0.75)),
        estimate(("A", "B"), ((0.04, 0.01), (0.01, 0.02))),
    )

    assert result is not None
    assert tuple(item.component_variance for item in result) == pytest.approx((0.004375, 0.013125))
    assert tuple(item.relative_contribution for item in result) == pytest.approx((0.25, 0.75))
    assert sum(item.relative_contribution for item in result) == pytest.approx(1.0)


def test_risk_contributions_preserve_negative_diversification_and_permutation() -> None:
    covariance = ((0.04, -0.015), (-0.015, 0.01))
    original = portfolio_risk_contributions(
        PortfolioWeights(("A", "B"), (0.1, 0.9)), estimate(("A", "B"), covariance)
    )
    permuted = portfolio_risk_contributions(
        PortfolioWeights(("B", "A"), (0.9, 0.1)),
        estimate(("B", "A"), ((0.01, -0.015), (-0.015, 0.04))),
    )

    assert original is not None and permuted is not None
    assert original[0].relative_contribution < 0
    assert {item.asset_id: item.relative_contribution for item in original} == pytest.approx(
        {item.asset_id: item.relative_contribution for item in permuted}
    )


@pytest.mark.parametrize("covariance", [((0.0,),), ((1e-16,),)])
def test_effectively_zero_variance_has_no_relative_attribution(
    covariance: tuple[tuple[float, ...], ...],
) -> None:
    assert (
        portfolio_risk_contributions(PortfolioWeights(("A",), (1.0,)), estimate(("A",), covariance))
        is None
    )
