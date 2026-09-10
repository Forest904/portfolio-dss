"""Portfolio risk attribution derived from an explicit covariance estimate."""

import math
from dataclasses import dataclass

from app.domain.errors import DomainValidationError
from app.domain.models import PortfolioWeights
from app.domain.optimization import RiskEstimate

ZERO_VARIANCE_TOLERANCE = 1e-15
CONTRIBUTION_SUM_TOLERANCE = 1e-8


@dataclass(frozen=True, slots=True)
class RiskContribution:
    asset_id: str
    component_variance: float
    relative_contribution: float


def portfolio_risk_contributions(
    weights: PortfolioWeights, risk: RiskEstimate
) -> tuple[RiskContribution, ...] | None:
    """Return Euler variance contributions, or ``None`` for effectively zero risk.

    Relative contributions are deliberately signed: a negative covariance contribution
    represents diversification and must not be silently clipped.
    """

    if weights.asset_ids != risk.asset_ids:
        raise DomainValidationError("risk contribution asset ordering must match")
    marginal = tuple(
        math.fsum(row[column] * weights.weights[column] for column in range(len(row)))
        for row in risk.covariance_matrix
    )
    components = tuple(
        weight * value for weight, value in zip(weights.weights, marginal, strict=True)
    )
    variance = math.fsum(components)
    if variance < -ZERO_VARIANCE_TOLERANCE:
        raise DomainValidationError("portfolio variance must not be negative")
    if variance <= ZERO_VARIANCE_TOLERANCE:
        return None
    relative = tuple(value / variance for value in components)
    if not math.isclose(math.fsum(relative), 1.0, rel_tol=0.0, abs_tol=CONTRIBUTION_SUM_TOLERANCE):
        raise DomainValidationError("relative risk contributions must sum to one")
    return tuple(
        RiskContribution(asset, component, share)
        for asset, component, share in zip(weights.asset_ids, components, relative, strict=True)
    )
