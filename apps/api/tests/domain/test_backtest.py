from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.application.backtest import build_engine, canonical_json
from app.domain.backtest import (
    BacktestConfig,
    BacktestEngine,
    BacktestPrices,
    EstimatorStrategy,
    StrategyDecision,
    TrainingWindow,
)
from app.domain.errors import DomainValidationError, OptimizationSolverError
from app.domain.models import PortfolioWeights
from app.domain.optimization import (
    AlignedReturnSample,
    ExpectedReturnSignal,
    HistoricalMeanEstimator,
    HistoricalSampleRiskEstimator,
    OptimizationRequest,
    OptimizationResult,
)
from app.infrastructure.optimization import ScipyMeanVarianceOptimizer


def fixture() -> tuple[BacktestConfig, BacktestPrices]:
    dates = tuple(date(2020, 1, 1) + timedelta(days=i) for i in range(10))
    config = BacktestConfig(
        ("A", "B"),
        dates[0],
        dates[-1],
        dates[3],
        dates[-1],
        training_returns=2,
        rebalance_sessions=2,
        initial_capital=100.0,
        max_weight=None,
    )
    prices = BacktestPrices(
        ("A", "B", "SPY"),
        dates,
        (
            (10.0, 11.0, 10.0, 20.0, 40.0, 20.0, 40.0, 20.0, 30.0, 45.0),
            (10.0, 9.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0),
            (10.0, 10.0, 10.0, 10.0, 11.0, 12.0, 11.0, 10.0, 12.0, 15.0),
        ),
    )
    return config, prices


class FixedStrategy:
    id = "fixed"
    identity = "fixed-v1"

    def decide(
        self,
        sample: AlignedReturnSample,
        window: TrainingWindow,
        executed_on: date,
        config: BacktestConfig,
    ) -> StrategyDecision:
        return StrategyDecision(executed_on, window, PortfolioWeights(sample.asset_ids, (0.5, 0.5)))


class SpyEstimator:
    def __init__(self) -> None:
        self.samples: list[AlignedReturnSample] = []

    def estimate(self, sample: AlignedReturnSample) -> ExpectedReturnSignal:
        self.samples.append(sample)
        return HistoricalMeanEstimator().estimate(sample)


class SpyOptimizer:
    def __init__(self) -> None:
        self.requests: list[OptimizationRequest] = []

    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        self.requests.append(request)
        return ScipyMeanVarianceOptimizer().optimize(request)


def test_hand_calculated_drift_rebalance_and_partial_interval() -> None:
    config, prices = fixture()
    config = replace(config, evaluation_end=prices.dates[8])
    report = BacktestEngine((FixedStrategy(),)).run(config, prices)
    fixed, equal, spy = report.strategies[0], report.strategies[-2], report.strategies[-1]
    assert [p.equity_usd for p in fixed.daily] == pytest.approx([100, 150, 100, 150, 100, 125])
    assert fixed.daily == equal.daily
    assert fixed.daily[1].closing_weights.weights == pytest.approx((2 / 3, 1 / 3))
    assert fixed.daily[2].closing_weights.weights == (0.5, 0.5)
    assert fixed.daily[0].daily_return is None
    assert fixed.performance.total_return == pytest.approx(0.25)
    assert fixed.performance.maximum_drawdown == pytest.approx(1 / 3)
    assert fixed.performance.annualized_return == pytest.approx(1.25 ** (252 / 5) - 1)
    assert [p.equity_usd for p in spy.daily] == pytest.approx([100, 110, 120, 110, 100, 120])
    assert len(spy.decisions) == 1
    assert [d.executed_on for d in equal.decisions] == [prices.dates[i] for i in (3, 5, 7)]


def test_training_windows_and_optimizer_receive_only_past_data() -> None:
    config, prices = fixture()
    estimator, optimizer = SpyEstimator(), SpyOptimizer()
    report = BacktestEngine(
        (EstimatorStrategy("spy", "spy-v1", estimator, HistoricalSampleRiskEstimator(), optimizer),)
    ).run(config, prices)
    for result in report.strategies[:2]:
        for index, decision in enumerate(result.decisions):
            training = decision.training
            assert training is not None
            assert training.return_end == decision.executed_on - timedelta(days=1)
            assert training.observations == (
                2 if result.window_mode == "rolling" else 2 + index * 2
            )
            expected_start = (
                prices.dates[index * 2] if result.window_mode == "rolling" else prices.dates[0]
            )
            assert training.price_start == expected_start
            assert training.return_start == expected_start + timedelta(days=1)
    assert len(estimator.samples) == len(optimizer.requests) == 8
    assert estimator.samples[0].returns[0] == pytest.approx((0.1, 10 / 11 - 1))
    for sample, request in zip(estimator.samples, optimizer.requests, strict=True):
        assert request.expected_returns.estimation_end == sample.observed_on[-1]
        assert request.risk_estimate.estimation_end == sample.observed_on[-1]
        assert request.risk_aversion == config.risk_aversion


def test_execution_and_future_price_changes_cannot_change_current_decision() -> None:
    config, prices = fixture()
    engine = build_engine(ScipyMeanVarianceOptimizer(), "test")
    original = engine.run(config, prices)
    for cutoff in (3, 5, 7):
        changed = replace(
            prices,
            adjusted_close=tuple(
                tuple(p if i < cutoff else p * (1.3 + i / 10) for i, p in enumerate(row))
                for row in prices.adjusted_close
            ),
        )
        altered = engine.run(config, changed)
        for before, after in zip(original.strategies, altered.strategies, strict=True):
            assert [d for d in before.decisions if d.executed_on <= prices.dates[cutoff]] == [
                d for d in after.decisions if d.executed_on <= prices.dates[cutoff]
            ]
            assert [p for p in before.daily if p.observed_on < prices.dates[cutoff]] == [
                p for p in after.daily if p.observed_on < prices.dates[cutoff]
            ]


def test_appending_future_preserves_prefix_even_at_rebalance_boundary() -> None:
    config, prices = fixture()
    engine = build_engine(ScipyMeanVarianceOptimizer(), "test")
    short_config = replace(config, history_end=prices.dates[7], evaluation_end=prices.dates[7])
    short_prices = replace(
        prices,
        dates=prices.dates[:8],
        adjusted_close=tuple(row[:8] for row in prices.adjusted_close),
    )
    short = engine.run(short_config, short_prices)
    full = engine.run(config, prices)
    for before, after in zip(short.strategies, full.strategies, strict=True):
        assert before.daily == after.daily[: len(before.daily)]
        assert before.decisions == after.decisions[: len(before.decisions)]


def test_six_comparable_series_constraints_and_reproducibility() -> None:
    config, prices = fixture()
    config = replace(config, max_weight=0.6)
    engine = build_engine(ScipyMeanVarianceOptimizer(), "test")
    report = engine.run(config, prices)
    assert canonical_json(report) == canonical_json(engine.run(config, prices))
    assert len(report.strategies) == 6
    for strategy in report.strategies:
        assert tuple(p.observed_on for p in strategy.daily) == prices.dates[3:]
        assert strategy.daily[0].equity_usd == 100
        for d in strategy.decisions:
            assert sum(d.target_weights.weights) == pytest.approx(1)
            assert min(d.target_weights.weights) >= 0
            if strategy.window_mode:
                assert max(d.target_weights.weights) <= 0.6 + 1e-8


@pytest.mark.parametrize(
    "changes",
    [
        {"training_returns": 0},
        {"training_returns": True},
        {"rebalance_sessions": 0},
        {"initial_capital": 0},
        {"initial_capital": float("nan")},
        {"risk_aversion": -1},
        {"risk_aversion": float("inf")},
        {"max_weight": 0.4},
        {"max_weight": True},
        {"tickers": ("A", "A")},
        {"tickers": ("SPY",)},
        {"window_modes": ()},
        {"window_modes": ("rolling", "rolling")},
        {"evaluation_start": date(2019, 1, 1)},
    ],
)
def test_invalid_configuration(changes: dict[str, object]) -> None:
    config, _ = fixture()
    with pytest.raises(DomainValidationError):
        replace(config, **changes)  # type: ignore[arg-type]  # Deliberately invalid inputs.


@pytest.mark.parametrize("price", [0, -1, float("nan"), float("inf")])
def test_invalid_prices(price: float) -> None:
    _, prices = fixture()
    with pytest.raises(DomainValidationError):
        replace(
            prices,
            adjusted_close=((price,) + prices.adjusted_close[0][1:], *prices.adjusted_close[1:]),
        )


def test_duplicate_dates_incomplete_data_and_insufficient_history() -> None:
    config, prices = fixture()
    with pytest.raises(DomainValidationError, match="ordered and unique"):
        replace(prices, dates=(prices.dates[1], *prices.dates[1:]))
    with pytest.raises(DomainValidationError, match="complete"):
        replace(prices, adjusted_close=(prices.adjusted_close[0][1:], *prices.adjusted_close[1:]))
    engine = BacktestEngine((FixedStrategy(),))
    with pytest.raises(DomainValidationError, match="warm-up"):
        engine.run(replace(config, training_returns=3), prices)
    with pytest.raises(DomainValidationError, match="two evaluation returns"):
        engine.run(replace(config, evaluation_start=prices.dates[-2]), prices)


class FailingOptimizer:
    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        raise OptimizationSolverError("deliberate failure")


def test_solver_failure_identifies_strategy_and_execution_date() -> None:
    config, prices = fixture()
    with pytest.raises(DomainValidationError, match="historical_mean_rolling at 2020-01-04"):
        build_engine(FailingOptimizer(), "failure").run(config, prices)


def test_single_asset_and_flat_market() -> None:
    config, prices = fixture()
    config = replace(config, tickers=("A",), max_weight=1.0)
    prices = replace(prices, asset_ids=("A", "SPY"), adjusted_close=((10.0,) * 10, (10.0,) * 10))
    report = build_engine(ScipyMeanVarianceOptimizer(), "test").run(config, prices)
    for strategy in report.strategies:
        assert strategy.performance.annualized_volatility == 0
        assert strategy.performance.total_return == 0
        assert strategy.performance.maximum_drawdown == 0
