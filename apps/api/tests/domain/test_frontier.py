from dataclasses import replace

import numpy as np
import pytest

from app.domain.errors import DomainValidationError, OptimizationSolverError
from app.domain.frontier import FrontierRequest, ProfileConfiguration
from app.infrastructure.frontier import ScipyEfficientFrontierGenerator
from tests.domain.test_optimization import optimization_request


def test_analytic_two_asset_frontier_and_profiles() -> None:
    source = optimization_request(means=(0.1, 0.2), covariance=((0.04, 0.0), (0.0, 0.09)))
    request = FrontierRequest(source.expected_returns, source.risk_estimate)
    result = ScipyEfficientFrontierGenerator().generate(request)
    assert len(result.points) == 21
    assert result.points[0].weights.weights == pytest.approx((9 / 13, 4 / 13), abs=1e-7)
    assert result.points[-1].weights.weights == pytest.approx((0, 1), abs=1e-8)
    for point in result.points:
        a, b = point.weights.weights
        assert a + b == pytest.approx(1, abs=1e-8)
        assert min(a, b) >= 0
        assert point.metrics.expected_return == pytest.approx(0.1 * a + 0.2 * b)
        assert point.metrics.expected_return == pytest.approx(point.target_return, abs=1e-8)
        assert point.metrics.variance == pytest.approx(0.04 * a * a + 0.09 * b * b)
    for left, right in zip(result.points, result.points[1:], strict=False):
        assert right.metrics.expected_return >= left.metrics.expected_return - 1e-8
        assert right.metrics.variance >= left.metrics.variance - 1e-8
    for profile, index in zip(result.profiles, (4, 10, 16), strict=True):
        assert profile.point_id == result.points[index].id


@pytest.mark.parametrize("cap", [0.5, 0.6, 1.0])
@pytest.mark.parametrize("means", [(0.1, 0.2), (-0.2, -0.1), (0.1, 0.1)])
def test_caps_negative_returns_and_equal_means(cap: float, means: tuple[float, float]) -> None:
    source = optimization_request(means=means, max_weight=cap)
    request = FrontierRequest(source.expected_returns, source.risk_estimate, source.constraints)
    result = ScipyEfficientFrontierGenerator().generate(request)
    assert all(max(point.weights.weights) <= cap + 1e-8 for point in result.points)
    if cap == 0.5 or means[0] == means[1]:
        assert len(result.points) == 1
        assert len({profile.point_id for profile in result.profiles}) == 1


def test_singular_minimum_variance_tie_prefers_highest_return() -> None:
    source = optimization_request(means=(0.1, 0.2), covariance=((0.04, 0.04), (0.04, 0.04)))
    result = ScipyEfficientFrontierGenerator().generate(
        FrontierRequest(source.expected_returns, source.risk_estimate)
    )
    assert len(result.points) == 1
    assert result.points[0].weights.weights == pytest.approx((0, 1))


def test_maximum_return_tie_prefers_lowest_variance() -> None:
    source = optimization_request(
        asset_ids=("A", "B", "C"),
        means=(0.2, 0.2, 0.1),
        covariance=((0.04, 0, 0), (0, 0.09, 0), (0, 0, 0.01)),
    )
    result = ScipyEfficientFrontierGenerator().generate(
        FrontierRequest(source.expected_returns, source.risk_estimate)
    )
    assert result.points[-1].weights.weights == pytest.approx((9 / 13, 4 / 13, 0), abs=1e-6)


@pytest.mark.parametrize("covariance", [((0.0, 0.0), (0.0, 0.0)), ((0.01, -0.01), (-0.01, 0.01))])
def test_zero_and_singular_covariance(covariance: tuple[tuple[float, ...], ...]) -> None:
    source = optimization_request(covariance=covariance)
    result = ScipyEfficientFrontierGenerator().generate(
        FrontierRequest(source.expected_returns, source.risk_estimate)
    )
    assert all(point.metrics.variance >= 0 for point in result.points)


def test_one_asset() -> None:
    source = optimization_request(asset_ids=("A",), means=(0.1,), covariance=((0.04,),))
    result = ScipyEfficientFrontierGenerator().generate(
        FrontierRequest(source.expected_returns, source.risk_estimate)
    )
    assert len(result.points) == 1
    assert result.points[0].weights.weights == (1.0,)


def test_custom_profiles_are_solved_exactly_and_repeatably() -> None:
    source = optimization_request()
    request = FrontierRequest(
        source.expected_returns,
        source.risk_estimate,
        profiles=ProfileConfiguration((0.23, 0.51, 0.87)),
    )
    generator = ScipyEfficientFrontierGenerator()
    result = generator.generate(request)
    assert result == generator.generate(request)
    assert len(result.points) == 24
    for profile in result.profiles:
        point = next(point for point in result.points if point.id == profile.point_id)
        assert point.metrics.expected_return == pytest.approx(profile.target_return, abs=1e-8)


def test_asset_permutation_preserves_economics() -> None:
    source = optimization_request()
    first = ScipyEfficientFrontierGenerator().generate(
        FrontierRequest(source.expected_returns, source.risk_estimate)
    )
    permuted = optimization_request(
        asset_ids=("B", "A"), means=(0.08, 0.15), covariance=((0.02, 0.01), (0.01, 0.09))
    )
    second = ScipyEfficientFrontierGenerator().generate(
        FrontierRequest(permuted.expected_returns, permuted.risk_estimate)
    )
    for left, right in zip(first.points, second.points, strict=True):
        assert left.weights.weights == pytest.approx(right.weights.weights[::-1], abs=1e-7)


def test_invalid_inputs_and_failed_solver() -> None:
    source = optimization_request()
    with pytest.raises(DomainValidationError):
        ProfileConfiguration((0.8, 0.5, 0.2))
    with pytest.raises(DomainValidationError):
        ProfileConfiguration((0.2, float("nan"), 0.8))
    with pytest.raises(DomainValidationError):
        FrontierRequest(
            source.expected_returns,
            source.risk_estimate,
            replace(source.constraints, max_weight=0.4),
        )
    bad_risk = replace(source.risk_estimate, covariance_matrix=((0.01, 0.1), (0.1, 0.01)))
    with pytest.raises(DomainValidationError, match="positive semidefinite"):
        ScipyEfficientFrontierGenerator().generate(
            FrontierRequest(source.expected_returns, bad_risk)
        )
    with pytest.raises(OptimizationSolverError):
        ScipyEfficientFrontierGenerator(maximum_iterations=1).generate(
            FrontierRequest(source.expected_returns, source.risk_estimate)
        )


def test_invalid_successful_solver_output_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    source = optimization_request()
    monkeypatch.setattr(
        "app.infrastructure.frontier.minimize",
        lambda *args, **kwargs: SimpleNamespace(
            success=True, x=np.array([0.9, 0.9]), status=0, message="ok", nit=1
        ),
    )
    with pytest.raises(OptimizationSolverError, match="verification"):
        ScipyEfficientFrontierGenerator().generate(
            FrontierRequest(source.expected_returns, source.risk_estimate)
        )
