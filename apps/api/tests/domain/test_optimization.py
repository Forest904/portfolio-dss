from datetime import date, timedelta

import pytest

from app.domain import (
    AlignedReturnSample,
    DomainValidationError,
    ExpectedReturnSignal,
    HistoricalMeanEstimator,
    HistoricalSampleRiskEstimator,
    MissingDataPolicy,
    OptimizationConstraints,
    OptimizationRequest,
    OptimizationSolverError,
    ReturnConvention,
    ReturnFrequency,
    RiskEstimate,
)
from app.infrastructure import ScipyMeanVarianceOptimizer


def return_sample() -> AlignedReturnSample:
    start = date(2026, 1, 2)
    return AlignedReturnSample(
        asset_ids=("AAA", "BBB"),
        observed_on=(start, start + timedelta(days=1)),
        returns=((0.01, 0.03), (-0.01, 0.01)),
        frequency=ReturnFrequency.DAILY,
        return_convention=ReturnConvention.SIMPLE,
        annualization_periods=2,
        missing_data_policy=MissingDataPolicy.NO_IMPUTATION,
    )


def optimization_request(
    *,
    asset_ids: tuple[str, ...] = ("A", "B"),
    means: tuple[float, ...] = (0.15, 0.08),
    covariance: tuple[tuple[float, ...], ...] = ((0.09, 0.01), (0.01, 0.02)),
    risk_aversion: float = 1.0,
    max_weight: float | None = None,
) -> OptimizationRequest:
    start = date(2025, 1, 1)
    end = date(2025, 12, 31)
    signal = ExpectedReturnSignal(
        asset_ids,
        means,
        ReturnFrequency.DAILY,
        ReturnConvention.SIMPLE,
        252,
        start,
        end,
        252,
        "fixture_mean",
    )
    risk = RiskEstimate(
        asset_ids,
        covariance,
        ReturnFrequency.DAILY,
        ReturnConvention.SIMPLE,
        252,
        start,
        end,
        252,
        MissingDataPolicy.NO_IMPUTATION,
        "fixture_covariance",
    )
    return OptimizationRequest(signal, risk, risk_aversion, OptimizationConstraints(max_weight))


def test_historical_estimators_annualize_known_mean_and_sample_covariance() -> None:
    sample = return_sample()

    signal = HistoricalMeanEstimator().estimate(sample)
    risk = HistoricalSampleRiskEstimator().estimate(sample)

    assert signal.asset_ids == ("AAA", "BBB")
    assert signal.expected_returns == pytest.approx((0.04, 0.0))
    assert signal.estimator_name == "historical_arithmetic_mean"
    assert risk.covariance_matrix[0] == pytest.approx((0.0004, 0.0004))
    assert risk.covariance_matrix[1] == pytest.approx((0.0004, 0.0004))
    assert risk.estimator_name == "historical_sample_covariance"
    assert risk.observations == 2


def test_return_sample_rejects_misaligned_and_non_finite_values() -> None:
    sample = return_sample()
    with pytest.raises(DomainValidationError, match="align"):
        AlignedReturnSample(
            sample.asset_ids,
            sample.observed_on,
            ((0.1,), (0.2, 0.3)),
            sample.frequency,
            sample.return_convention,
            sample.annualization_periods,
            sample.missing_data_policy,
        )
    with pytest.raises(DomainValidationError, match="finite"):
        AlignedReturnSample(
            sample.asset_ids,
            sample.observed_on,
            ((0.1, float("nan")), (0.2, 0.3)),
            sample.frequency,
            sample.return_convention,
            sample.annualization_periods,
            sample.missing_data_policy,
        )


def test_optimizer_satisfies_invariants_cap_and_reported_metrics() -> None:
    request = optimization_request(risk_aversion=0.0, max_weight=0.6)

    result = ScipyMeanVarianceOptimizer().optimize(request)

    assert sum(result.weights.weights) == pytest.approx(1.0, abs=1e-8)
    assert min(result.weights.weights) >= 0.0
    assert max(result.weights.weights) <= 0.6 + 1e-8
    expected_return = sum(
        weight * mean
        for weight, mean in zip(
            result.weights.weights,
            request.expected_returns.expected_returns,
            strict=True,
        )
    )
    variance = sum(
        result.weights.weights[row]
        * request.risk_estimate.covariance_matrix[row][column]
        * result.weights.weights[column]
        for row in range(2)
        for column in range(2)
    )
    assert result.metrics.expected_return == pytest.approx(expected_return)
    assert result.metrics.variance == pytest.approx(variance)
    assert result.metrics.volatility == pytest.approx(variance**0.5)
    assert result.metrics.objective_value == pytest.approx(
        expected_return - request.risk_aversion * variance
    )
    assert result.solver.success
    assert result.constraint_status == "valid"
    assert "A" in result.solver.binding_asset_ids


def test_higher_risk_aversion_does_not_increase_variance() -> None:
    optimizer = ScipyMeanVarianceOptimizer()
    low = optimizer.optimize(optimization_request(risk_aversion=0.1))
    high = optimizer.optimize(optimization_request(risk_aversion=10.0))

    assert high.metrics.variance <= low.metrics.variance + 1e-8


def test_zero_risk_aversion_maximizes_return_and_permutation_is_economic_equivalent() -> None:
    optimizer = ScipyMeanVarianceOptimizer()
    original = optimizer.optimize(optimization_request(risk_aversion=0.0))
    permuted = optimizer.optimize(
        optimization_request(
            asset_ids=("B", "A"),
            means=(0.08, 0.15),
            covariance=((0.02, 0.01), (0.01, 0.09)),
            risk_aversion=0.0,
        )
    )

    assert dict(
        zip(original.weights.asset_ids, original.weights.weights, strict=True)
    ) == pytest.approx(dict(zip(permuted.weights.asset_ids, permuted.weights.weights, strict=True)))
    assert original.weights.weights == pytest.approx((1.0, 0.0), abs=1e-7)


def test_single_asset_and_singular_covariance_are_supported() -> None:
    single = ScipyMeanVarianceOptimizer().optimize(
        optimization_request(
            asset_ids=("ONLY",), means=(-0.1,), covariance=((0.0,),), risk_aversion=4.0
        )
    )
    tied = ScipyMeanVarianceOptimizer().optimize(
        optimization_request(
            means=(0.1, 0.1),
            covariance=((0.04, 0.04), (0.04, 0.04)),
            risk_aversion=1.0,
        )
    )

    assert single.weights.weights == (1.0,)
    assert tied.weights.weights == pytest.approx((0.5, 0.5))


def test_invalid_constraints_covariance_and_non_convergence_are_rejected() -> None:
    with pytest.raises(DomainValidationError, match="infeasible"):
        optimization_request(max_weight=0.4)
    with pytest.raises(DomainValidationError, match="symmetric"):
        optimization_request(covariance=((0.1, 0.02), (0.01, 0.1)))
    with pytest.raises(DomainValidationError, match="dimensions"):
        optimization_request(covariance=((0.1,), (0.01,)))
    with pytest.raises(DomainValidationError, match="positive semidefinite"):
        ScipyMeanVarianceOptimizer().optimize(
            optimization_request(covariance=((0.01, 0.02), (0.02, 0.01)))
        )
    with pytest.raises(OptimizationSolverError):
        ScipyMeanVarianceOptimizer(maximum_iterations=0).optimize(optimization_request())
