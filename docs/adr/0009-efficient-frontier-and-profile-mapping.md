# ADR 0009 — Efficient frontier and profile mapping

- Status: Accepted
- Date: 2026-09-08

## Context

Week 5 makes feasible risk/return trade-offs visible without making the user select a mathematical
risk-aversion coefficient. The Week 4 lambda objective remains available and unchanged. Historical
CAGR is not comparable to the arithmetic expected-return estimate on a frontier.

## Decision

- Introduce an independent `EfficientFrontierGenerator` protocol consuming `ExpectedReturnSignal`,
  `RiskEstimate`, constraints, and a typed profile configuration. SciPy remains an infrastructure
  adapter; the domain has no framework or numerical-library dependency.
- Minimize portfolio variance with budget, long-only, optional uniform cap, and exact target-return
  constraints. Use SLSQP with analytic gradients, objective scaling, `ftol=1e-12`, and at most 1,000
  iterations. Scale the return constraint by the spread of asset means.
- Start at the global minimum-variance portfolio. For singular covariance, maximize return over its
  covariance-nullspace equivalence class using HiGHS linear programming. Eigenvalues below the
  relative `1e-12` rank threshold are treated as numerical nullspace. Verify the tie preserves
  variance within `1e-8`.
- Find maximum achievable return by linear programming; minimize variance at that exact target to
  resolve maximum-return ties. A deterministic interpolation between feasible endpoint allocations
  supplies feasible starting weights for intermediate target solves.
- Generate 21 evenly spaced targets over that return interval and include exact configured profile
  targets. Conservative/moderate/aggressive default to fractions `0.2`, `0.5`, `0.8`. Fractions are
  strictly increasing and within `[0, 1]`; their semantics are versioned as
  `frontier-return-fractions-v1`. They are modeling preferences, not calibrated suitability scores,
  loss probabilities, percentages of volatility, or universal risk categories.
- Independently verify finite allocations, budget, nonnegative weights, cap, target return, and
  increasing return/variance within absolute `1e-8`. Tiny bound residuals may be clipped and
  normalized only with another verification afterward. Recompute all metrics from model inputs.
  Deduplicate points whose return and variance both agree within `1e-10`. Return spans at most
  `1e-12` collapse to the minimum-variance endpoint; preserve all profile references.
- Fetch selected stocks and SPY in one request and align them once. All model estimates use the same
  daily simple returns, adjusted-close prices, and 252-period annualization. SPY is a reference,
  never an investable optimization asset. Benchmark gaps or unavailability fail the report through
  existing error conventions rather than silently changing the comparison.
- Report estimated metrics without a lambda objective. Current and equal-weight references use
  the same selected-asset model; current weights use ending market values. Report cap violations
  for references; mark SPY as outside the investable universe.
- Produce typed numerical decision facts and deterministic UI templates. Return/volatility and
  allocation differences use percentage points; holding weights use fractions; HHI is dimensionless.
  Do not infer causal portfolio-change rationale from numerical differences.
- Hash effective model inputs, results, constraints, mapping, conventions, assumptions, and provenance
  content hashes. Exclude retrieval timestamps. Reproducibility applies to identical inputs and the
  same numerical environment; cross-platform floating-point bit identity is not promised.

## Consequences

Profiles can coincide under restrictive constraints or degenerate inputs; the UI states this rather
than inventing trade-offs. A selected-stock frontier is not the frontier of the whole market, so SPY
may appear beyond it. Including SPY can shorten the common history window relative to the Week 4
endpoint. Estimated arithmetic metrics remain visually distinct from observed historical CAGR.

The questionnaire and capital-based flow remain Week 6 work. This configuration is the reusable
mapping boundary for that flow; it does not introduce a questionnaire now. Monte Carlo and richer
causal explanations remain later milestones.
