"""Explainable finite-sample exponential mean; no fitting or external dependencies."""

import math

from app.domain.optimization import AlignedReturnSample, ExpectedReturnSignal

HALF_LIFE = 63


def exponential_weights(observations: int) -> tuple[float, ...]:
    if observations < 2:
        raise ValueError("At least two observations are required")
    raw = tuple(2 ** (-age / HALF_LIFE) for age in reversed(range(observations)))
    total = math.fsum(raw)
    return tuple(weight / total for weight in raw)


class SimpleForecastEstimator:
    """Annualized, normalized exponentially weighted daily simple-return mean."""

    def estimate(self, sample: AlignedReturnSample) -> ExpectedReturnSignal:
        weights = exponential_weights(len(sample.observed_on))
        values = tuple(
            math.fsum(w * r for w, r in zip(weights, row, strict=True))
            * sample.annualization_periods
            for row in sample.returns
        )
        diagnostics: tuple[str, ...] = (
            "Normalized exponential weights use a fixed 63-trading-observation half-life.",
            "The future daily mean is assumed constant; annualization is arithmetic, not CAGR.",
            "Predictive accuracy has not been evaluated; estimates are not guaranteed outcomes.",
        )
        if len(weights) < HALF_LIFE:
            diagnostics += ("Short history: fewer than 63 return observations are available.",)
        return ExpectedReturnSignal(
            asset_ids=sample.asset_ids,
            frequency=sample.frequency,
            return_convention=sample.return_convention,
            annualization_periods=sample.annualization_periods,
            estimation_start=sample.observed_on[0],
            estimation_end=sample.observed_on[-1],
            observations=len(sample.observed_on),
            expected_returns=values,
            estimator_name="simple_exponential_forecast",
            diagnostics=diagnostics,
        )
