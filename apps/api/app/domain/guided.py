"""Deterministic preference and illustrative capital allocation rules."""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal, localcontext
from typing import Literal

from app.domain.errors import DomainValidationError
from app.domain.frontier import PROFILE_NAMES, ProfileName
from app.domain.models import PortfolioWeights

PREFERENCE_VERSION = "guided-preferences-v1"
QuestionId = Literal["trade_off", "fluctuations", "decline"]
QUESTIONS: tuple[QuestionId, ...] = ("trade_off", "fluctuations", "decline")


@dataclass(frozen=True, slots=True)
class PreferenceAnswers:
    trade_off: ProfileName
    fluctuations: ProfileName
    decline: ProfileName


@dataclass(frozen=True, slots=True)
class PreferenceResult:
    answers: PreferenceAnswers
    version: str
    suggested_profile: ProfileName
    determining_answers: tuple[QuestionId, ...]
    explanation: str


def map_preferences(
    answers: PreferenceAnswers,
    version: str = PREFERENCE_VERSION,
) -> PreferenceResult:
    values = tuple(getattr(answers, question) for question in QUESTIONS)
    if version != PREFERENCE_VERSION or any(value not in PROFILE_NAMES for value in values):
        raise DomainValidationError("Unsupported questionnaire version or answer")
    profile = min(values, key=PROFILE_NAMES.index)
    determining = tuple(q for q, value in zip(QUESTIONS, values, strict=True) if value == profile)
    labels = {
        "trade_off": "return/stability trade-off",
        "fluctuations": "comfort with fluctuations",
        "decline": "response to a hypothetical decline",
    }
    return PreferenceResult(
        answers,
        version,
        profile,
        determining,
        f"Your {', '.join(labels[q] for q in determining)} determined the {profile} suggestion. "
        "We use your lowest expressed tolerance for risk. This is a relative stocks-only "
        "preference, not a suitability assessment or a promise of capital protection.",
    )


def validate_capital(capital: Decimal) -> Decimal:
    exponent = capital.as_tuple().exponent
    if not capital.is_finite() or capital <= 0 or not isinstance(exponent, int) or exponent < -2:
        raise DomainValidationError("Enter positive USD capital with at most two decimal places")
    return capital


@dataclass(frozen=True, slots=True)
class DollarAllocation:
    asset_id: str
    weight: float
    amount: Decimal


def allocate_capital(capital: Decimal, weights: PortfolioWeights) -> tuple[DollarAllocation, ...]:
    validate_capital(capital)
    with localcontext() as context:
        context.prec = max(40, len(capital.as_tuple().digits) + 25)
        cents = int(capital * 100)
        decimal_weights = tuple(Decimal(str(w)) for w in weights.weights)
        total = sum(decimal_weights)
        exact = tuple(cents * w / total for w in decimal_weights)
        rounded = [int(v.to_integral_value(rounding=ROUND_FLOOR)) for v in exact]
        order = sorted(
            range(len(exact)), key=lambda i: (-(exact[i] - rounded[i]), weights.asset_ids[i])
        )
        for i in order[: cents - sum(rounded)]:
            rounded[i] += 1
        return tuple(
            DollarAllocation(asset, weight, Decimal(value) / 100)
            for asset, weight, value in zip(
                weights.asset_ids, weights.weights, rounded, strict=True
            )
        )
