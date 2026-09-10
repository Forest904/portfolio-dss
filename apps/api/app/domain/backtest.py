"""Deterministic, close-to-close walk-forward accounting without external dependencies."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from app.domain.conventions import DEFAULT_FINANCIAL_CONVENTIONS, FinancialConventions
from app.domain.errors import DomainValidationError, OptimizationSolverError
from app.domain.models import PortfolioWeights
from app.domain.optimization import (
    AlignedReturnSample,
    ExpectedReturnEstimator,
    ExpectedReturnSignal,
    OptimizationConstraints,
    OptimizationRequest,
    PortfolioOptimizer,
    RiskEstimate,
    RiskEstimator,
    SolverDiagnostics,
)

WindowMode = Literal["rolling", "expanding"]


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    tickers: tuple[str, ...]
    history_start: date
    history_end: date
    evaluation_start: date
    evaluation_end: date
    window_modes: tuple[WindowMode, ...] = ("rolling", "expanding")
    training_returns: int = 252
    rebalance_sessions: int = 21
    initial_capital: float = 10_000.0
    risk_aversion: float = 3.0
    max_weight: float | None = 0.4

    def __post_init__(self) -> None:
        if (
            not self.tickers
            or len(set(self.tickers)) != len(self.tickers)
            or any(not t or t != t.strip().upper() or t == "SPY" for t in self.tickers)
        ):
            raise DomainValidationError("tickers must be unique uppercase stocks, excluding SPY")
        if not self.history_start < self.evaluation_start < self.evaluation_end <= self.history_end:
            raise DomainValidationError("history must contain the training and evaluation windows")
        if (
            not self.window_modes
            or len(set(self.window_modes)) != len(self.window_modes)
            or any(mode not in ("rolling", "expanding") for mode in self.window_modes)
        ):
            raise DomainValidationError("window_modes must contain unique rolling/expanding values")
        for name, value, minimum in (
            ("training_returns", self.training_returns, 2),
            ("rebalance_sessions", self.rebalance_sessions, 1),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise DomainValidationError(f"{name} must be an integer >= {minimum}")
        for name, amount in (
            ("initial_capital", self.initial_capital),
            ("risk_aversion", self.risk_aversion),
        ):
            if isinstance(amount, bool) or not math.isfinite(amount) or amount < 0:
                raise DomainValidationError(f"{name} must be finite and non-negative")
        if self.initial_capital == 0:
            raise DomainValidationError("initial_capital must be positive")
        OptimizationConstraints(self.max_weight)
        if self.max_weight is not None and self.max_weight * len(self.tickers) < 1 - 1e-8:
            raise DomainValidationError("max_weight makes the budget constraint infeasible")


@dataclass(frozen=True, slots=True)
class BacktestPrices:
    asset_ids: tuple[str, ...]
    dates: tuple[date, ...]
    adjusted_close: tuple[tuple[float, ...], ...]
    conventions: FinancialConventions = DEFAULT_FINANCIAL_CONVENTIONS

    def __post_init__(self) -> None:
        if not self.asset_ids or len(set(self.asset_ids)) != len(self.asset_ids):
            raise DomainValidationError("price assets must be unique and non-empty")
        if not self.dates or any(a >= b for a, b in zip(self.dates, self.dates[1:], strict=False)):
            raise DomainValidationError("price dates must be ordered and unique")
        if len(self.adjusted_close) != len(self.asset_ids) or any(
            len(row) != len(self.dates) or any(not math.isfinite(p) or p <= 0 for p in row)
            for row in self.adjusted_close
        ):
            raise DomainValidationError("prices must be complete, finite, positive and aligned")
        if self.conventions != DEFAULT_FINANCIAL_CONVENTIONS:
            raise DomainValidationError("backtests require daily USD adjusted-close conventions")


@dataclass(frozen=True, slots=True)
class TrainingWindow:
    price_start: date
    return_start: date
    return_end: date
    observations: int


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    executed_on: date
    training: TrainingWindow | None
    target_weights: PortfolioWeights
    expected_returns: ExpectedReturnSignal | None = None
    risk_estimate: RiskEstimate | None = None
    solver: SolverDiagnostics | None = None


class AllocationStrategy(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def identity(self) -> str: ...

    def decide(
        self,
        sample: AlignedReturnSample,
        window: TrainingWindow,
        executed_on: date,
        config: BacktestConfig,
    ) -> StrategyDecision: ...


@dataclass(frozen=True, slots=True)
class EstimatorStrategy:
    id: str
    identity: str
    estimator: ExpectedReturnEstimator
    risk_estimator: RiskEstimator
    optimizer: PortfolioOptimizer

    def decide(
        self,
        sample: AlignedReturnSample,
        window: TrainingWindow,
        executed_on: date,
        config: BacktestConfig,
    ) -> StrategyDecision:
        signal = self.estimator.estimate(sample)
        risk = self.risk_estimator.estimate(sample)
        result = self.optimizer.optimize(
            OptimizationRequest(
                signal,
                risk,
                config.risk_aversion,
                OptimizationConstraints(config.max_weight),
            )
        )
        return StrategyDecision(executed_on, window, result.weights, signal, risk, result.solver)


@dataclass(frozen=True, slots=True)
class DailyBacktestResult:
    observed_on: date
    equity_usd: float
    daily_return: float | None
    drawdown: float
    closing_weights: PortfolioWeights


@dataclass(frozen=True, slots=True)
class BacktestPerformance:
    total_return: float
    annualized_return: float
    annualized_volatility: float
    maximum_drawdown: float
    terminal_value_usd: float


@dataclass(frozen=True, slots=True)
class StrategyResult:
    id: str
    identity: str
    window_mode: WindowMode | None
    daily: tuple[DailyBacktestResult, ...]
    decisions: tuple[StrategyDecision, ...]
    performance: BacktestPerformance


@dataclass(frozen=True, slots=True)
class BacktestReport:
    config: BacktestConfig
    conventions: FinancialConventions
    strategies: tuple[StrategyResult, ...]
    version: str = "walk-forward-v1"


class BacktestEngine:
    def __init__(self, strategies: tuple[AllocationStrategy, ...]) -> None:
        if not strategies or len({s.id for s in strategies}) != len(strategies):
            raise DomainValidationError("strategies must have unique identifiers")
        self._strategies = strategies

    def run(self, config: BacktestConfig, prices: BacktestPrices) -> BacktestReport:
        if prices.asset_ids != (*config.tickers, "SPY"):
            raise DomainValidationError("price order must match tickers followed by SPY")
        if prices.dates[0] < config.history_start or prices.dates[-1] > config.history_end:
            raise DomainValidationError("prices must lie within configured history")
        evaluation = [
            i
            for i, d in enumerate(prices.dates)
            if config.evaluation_start <= d <= config.evaluation_end
        ]
        if len(evaluation) < 3:
            raise DomainValidationError("at least two evaluation returns are required")
        first, last = evaluation[0], evaluation[-1]
        # t-1 must have N preceding return intervals: N+1 prices before execution t.
        if first < config.training_returns + 1:
            raise DomainValidationError(
                f"insufficient warm-up: need {config.training_returns + 1} prices before "
                f"{prices.dates[first]}, found {first}; extend history_start"
            )
        results = [
            self._run_strategy(config, prices, first, last, strategy, mode)
            for mode in config.window_modes
            for strategy in self._strategies
        ]
        results.extend(
            self._run_strategy(config, prices, first, last, None, None, baseline)
            for baseline in ("equal_weight", "sp500_proxy")
        )
        return BacktestReport(config, prices.conventions, tuple(results))

    def _run_strategy(
        self,
        config: BacktestConfig,
        prices: BacktestPrices,
        first: int,
        last: int,
        strategy: AllocationStrategy | None,
        mode: WindowMode | None,
        baseline: str = "",
    ) -> StrategyResult:
        identifier = f"{strategy.id}_{mode}" if strategy else baseline
        asset_ids = ("SPY",) if baseline == "sp500_proxy" else config.tickers
        rows = (
            prices.adjusted_close[-1:]
            if baseline == "sp500_proxy"
            else (prices.adjusted_close[:-1])
        )
        values = [config.initial_capital / len(asset_ids)] * len(asset_ids)
        daily: list[DailyBacktestResult] = []
        decisions: list[StrategyDecision] = []
        previous = peak = config.initial_capital
        for t in range(first, last + 1):
            try:
                if t > first:
                    values = [v * row[t] / row[t - 1] for v, row in zip(values, rows, strict=True)]
                equity = math.fsum(values)
                if not math.isfinite(equity) or equity <= 0:
                    raise DomainValidationError("nonfinite or nonpositive portfolio equity")
                rebalance = t == first or (
                    baseline != "sp500_proxy" and (t - first) % config.rebalance_sessions == 0
                )
                if rebalance:
                    if strategy:
                        start = (t if mode == "rolling" else first) - config.training_returns - 1
                        window = TrainingWindow(
                            prices.dates[start],
                            prices.dates[start + 1],
                            prices.dates[t - 1],
                            t - start - 1,
                        )
                        sample = AlignedReturnSample(
                            config.tickers,
                            prices.dates[start + 1 : t],
                            tuple(
                                tuple(row[j] / row[j - 1] - 1 for j in range(start + 1, t))
                                for row in rows
                            ),
                            prices.conventions.return_frequency,
                            prices.conventions.return_convention,
                            prices.conventions.annualization_periods,
                            prices.conventions.missing_data_policy,
                        )
                        decision = strategy.decide(sample, window, prices.dates[t], config)
                        if decision.training != window or decision.executed_on != prices.dates[t]:
                            raise DomainValidationError(
                                "strategy returned mismatched decision dates"
                            )
                    else:
                        decision = StrategyDecision(
                            prices.dates[t],
                            None,
                            PortfolioWeights(asset_ids, (1 / len(asset_ids),) * len(asset_ids)),
                        )
                    weights = decision.target_weights
                    if weights.asset_ids != asset_ids or any(w < 0 for w in weights.weights):
                        raise DomainValidationError("invalid strategy weights or asset ordering")
                    if (
                        strategy
                        and config.max_weight is not None
                        and any(w > config.max_weight + 1e-8 for w in weights.weights)
                    ):
                        raise DomainValidationError("strategy exceeds maximum weight")
                    values = [equity * w for w in weights.weights]
                    decisions.append(decision)
                peak = max(peak, equity)
                daily.append(
                    DailyBacktestResult(
                        prices.dates[t],
                        equity,
                        None if t == first else equity / previous - 1,
                        equity / peak - 1,
                        PortfolioWeights(asset_ids, tuple(v / equity for v in values)),
                    )
                )
                previous = equity
            except (ValueError, ArithmeticError, OptimizationSolverError) as exc:
                raise DomainValidationError(f"{identifier} at {prices.dates[t]}: {exc}") from exc
        returns = tuple(point.daily_return for point in daily if point.daily_return is not None)
        ratio = daily[-1].equity_usd / config.initial_capital
        performance = BacktestPerformance(
            ratio - 1,
            ratio ** (prices.conventions.annualization_periods / len(returns)) - 1,
            statistics.stdev(returns) * math.sqrt(prices.conventions.annualization_periods),
            -min(point.drawdown for point in daily),
            daily[-1].equity_usd,
        )
        if any(
            not math.isfinite(v)
            for v in (
                performance.total_return,
                performance.annualized_return,
                performance.annualized_volatility,
                performance.maximum_drawdown,
            )
        ):
            raise DomainValidationError(f"{identifier}: nonfinite performance")
        return StrategyResult(
            identifier,
            strategy.identity if strategy else f"{baseline}-v1",
            mode,
            tuple(daily),
            tuple(decisions),
            performance,
        )
