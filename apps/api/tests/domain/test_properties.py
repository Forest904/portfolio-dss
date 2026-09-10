"""Seeded generative checks for cross-cutting numerical invariants."""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain import (
    MissingDataPolicy,
    PortfolioWeights,
    ReturnConvention,
    ReturnFrequency,
    RiskEstimate,
    portfolio_risk_contributions,
)
from app.domain.guided import allocate_capital


@given(
    st.lists(
        st.integers(min_value=1, max_value=10_000),
        min_size=1,
        max_size=12,
    ),
    st.integers(min_value=1, max_value=10_000_000),
)
def test_dollar_allocation_always_preserves_every_cent(raw_weights: list[int], cents: int) -> None:
    total = sum(raw_weights)
    weights = PortfolioWeights(
        tuple(f"S{index:02}" for index in range(len(raw_weights))),
        tuple(value / total for value in raw_weights),
    )
    allocation = allocate_capital(Decimal(cents) / 100, weights)

    assert sum((item.amount for item in allocation), Decimal(0)) == Decimal(cents) / 100
    assert all(item.amount >= 0 for item in allocation)


@given(
    st.lists(
        st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=10,
    ),
    st.lists(st.integers(min_value=1, max_value=1000), min_size=1, max_size=10),
)
def test_diagonal_risk_contributions_sum_and_survive_permutation(
    variances: list[float], raw_weights: list[int]
) -> None:
    size = min(len(variances), len(raw_weights))
    variances, raw_weights = variances[:size], raw_weights[:size]
    total = sum(raw_weights)
    ids = tuple(f"S{index:02}" for index in range(size))
    weights = tuple(value / total for value in raw_weights)
    covariance = tuple(
        tuple(variances[row] if row == column else 0.0 for column in range(size))
        for row in range(size)
    )

    def risk(asset_ids: tuple[str, ...], matrix: tuple[tuple[float, ...], ...]) -> RiskEstimate:
        return RiskEstimate(
            asset_ids,
            matrix,
            ReturnFrequency.DAILY,
            ReturnConvention.SIMPLE,
            252,
            date(2025, 1, 1),
            date(2025, 12, 31),
            252,
            MissingDataPolicy.NO_IMPUTATION,
            "generated-diagonal",
        )

    original = portfolio_risk_contributions(PortfolioWeights(ids, weights), risk(ids, covariance))
    order = tuple(reversed(range(size)))
    permuted_ids = tuple(ids[index] for index in order)
    permuted_covariance = tuple(tuple(covariance[row][column] for column in order) for row in order)
    permuted = portfolio_risk_contributions(
        PortfolioWeights(permuted_ids, tuple(weights[index] for index in order)),
        risk(permuted_ids, permuted_covariance),
    )

    assert original is not None and permuted is not None
    assert sum(item.relative_contribution for item in original) == pytest.approx(1.0)
    assert {item.asset_id: item.relative_contribution for item in original} == pytest.approx(
        {item.asset_id: item.relative_contribution for item in permuted}
    )
