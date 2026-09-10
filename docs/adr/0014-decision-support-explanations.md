# ADR 0014 — Deterministic decision-support explanations

- Status: Accepted
- Date: 2026-09-10

## Context

The frontier report already exposed exact return, volatility, allocation, concentration and cap
facts. Those values described what changed, but a flat fact list did not help a non-expert connect
the recommendation to the model inputs. ADR 0009 deliberately deferred causal portfolio-change
rationale until a later milestone.

## Decision

- Attribute modeled portfolio risk with Euler variance contributions. For asset `i`, component
  variance is `w_i * (Sigma w)_i`; its relative contribution divides this value by
  `w' Sigma w`. Contributions remain signed because a negative value can represent a genuine
  diversification effect. Relative contributions must sum to one within `1e-8`.
- Treat variance at or below `1e-15` as effectively zero. Do not divide by it or invent relative
  shares; omit those facts, emit a diagnostic and use other evidence in the explanation.
- Existing-holdings reports explain each profile against current end-date weights. Guided reports
  use equal weight across the eligible universe. SPY remains a comparable reference, not the
  explanation baseline or an investable asset.
- Extend typed facts with asset return estimates, baseline-relative allocation/risk/concentration
  changes and equivalent-profile flags. Preserve exact facts separately from presentation text.
- Use the versioned `decision-explanations-v1` rules. Always describe the return/volatility
  trade-off; consider allocation changes from 0.5 percentage points, return/volatility changes
  from 0.1 percentage points and HHI changes from 0.01; prioritize binding constraints and
  coincident profiles; return three to five reasons with stable tie-breaking.
- Each reason carries the IDs of the facts supporting it. English text is deterministic. Holding
  evidence is described as supporting a joint expected-return/covariance decision, never as a
  proof that one isolated metric caused a weight.
- Do not claim estimator-driven allocation sensitivity: the current report solves only with the
  selected estimator. The fixed-weight two-estimator comparison remains available as model
  evidence.
- Add explanations to the report hash and bump the frontier cache signature. SQLite guided-cache
  schema version 3 clears incompatible model blobs and converts completed legacy reports into
  retryable `REPORT_VERSION_CHANGED` failures.

## Consequences

The primary result view can answer why a target differs from its relevant baseline while retaining
an auditable path to numerical facts. Explanations remain limited by estimated means, historical
covariance and the explicit long-only constraints. They do not include transaction costs, taxes,
turnover, suitability assessment, or a guarantee that the proposed change will improve outcomes.
