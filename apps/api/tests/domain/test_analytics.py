from datetime import date, timedelta

import pytest

from app.domain import calculate_historical_analytics, concentration


def test_calculates_known_buy_and_hold_performance_and_concentration() -> None:
    start = date(2025, 1, 2)
    dates = tuple(start + timedelta(days=index) for index in range(3))
    result = calculate_historical_analytics(
        asset_ids=("AAA", "BBB"),
        benchmark_asset_id="SPY",
        dates=dates,
        prices={
            "AAA": (100.0, 110.0, 121.0),
            "BBB": (100.0, 100.0, 100.0),
            "SPY": (100.0, 105.0, 110.25),
        },
        quantities=(1.0, 1.0),
        sectors=("Growth", "Defensive"),
        annualization_periods=2,
    )

    assert result.current_series[0].daily_return is None
    assert result.current_series[0].cumulative_return == 0.0
    assert result.current_performance.total_return == pytest.approx(0.105)
    assert result.current_performance.annualized_return == pytest.approx(0.105)
    assert result.equal_weight_performance.total_return == pytest.approx(0.105)
    assert result.benchmark_performance.total_return == pytest.approx(0.1025)
    assert result.ending_asset_weights == pytest.approx((121 / 221, 100 / 221))
    assert result.asset_concentration.largest_id == "AAA"
    assert result.sector_concentration.components[0].id == "Growth"


def test_covariance_is_symmetric_and_zero_variance_correlation_is_undefined() -> None:
    start = date(2025, 1, 2)
    result = calculate_historical_analytics(
        asset_ids=("AAA", "FLAT"),
        benchmark_asset_id="SPY",
        dates=tuple(start + timedelta(days=index) for index in range(4)),
        prices={
            "AAA": (100.0, 110.0, 99.0, 118.8),
            "FLAT": (50.0, 50.0, 50.0, 50.0),
            "SPY": (100.0, 101.0, 102.0, 103.0),
        },
        quantities=(1.0, 1.0),
        sectors=("One", "Two"),
        annualization_periods=252,
    )

    covariance = result.covariance.values
    assert covariance[0][1] == pytest.approx(covariance[1][0])
    assert covariance[1][1] == pytest.approx(0.0)
    assert result.correlation.values[0][0] == pytest.approx(1.0)
    assert result.correlation.values[0][1] is None
    assert result.correlation.values[1][1] is None
    assert result.undefined_correlation_assets == ("FLAT",)


def test_concentration_reports_hhi_top_three_and_effective_count() -> None:
    result = concentration({"A": 0.5, "B": 0.3, "C": 0.15, "D": 0.05})

    assert result.largest_weight == 0.5
    assert result.top_three_weight == pytest.approx(0.95)
    assert result.hhi == pytest.approx(0.365)
    assert result.effective_count == pytest.approx(1 / 0.365)
