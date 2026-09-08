# ADR 0010 — Guided portfolio construction

- Status: Accepted
- Date: 2026-09-08

## Decision

The primary journey builds a new portfolio from USD capital and three required preference answers.
`guided-preferences-v1` selects the least aggressive answer and records every determining question.
These are relative modeling preferences, not calibrated suitability scores. Reuse ADR 0009's
configured profile fractions and frontier solver; apply one common 10% per-stock cap.

Screen every current constituent ticker. A separate typed bulk-history port reports successful
series and explicit failures. Its adapter requests batches of 25, with at most two concurrent
batches, and retries failed tickers once individually through the existing cached provider.
Existing holdings endpoints retain their strict retrieval and alignment behavior.

SPY is reference-only. Eligible stocks require USD adjusted-close prices on every observed SPY
session in the requested three-calendar-year window. Require at least 253 SPY observations,
90% constituent coverage, and ten eligible stocks. Exclude incomplete stocks explicitly without
imputation. The 90% threshold is an operational coverage rule, not a financial calibration.

The shared frontier calculation accepts an aligned snapshot and optional real holdings. New
construction reports contain equal-weight and SPY references, with no fabricated current portfolio.
Capital does not enter estimation or optimization. Decimal largest-remainder rounding reconciles
illustrative dollar amounts to cents, with ticker-order ties; mathematical weights remain unchanged.

Use SQLite jobs and one supervised spawned calculation process inside the API deployment.
A local file lease rejects a second API process using the same jobs database. Run Uvicorn with
one worker. The supervisor terminates calculations after 900 seconds and marks interrupted jobs
retryable on restart. Jobs expire after 24 hours. Identical in-flight requests share a model run;
the validated effective-data cache lasts six hours. Effective observations, membership, conventions,
model implementation identities/version, profile configuration, eligibility and constraints enter
the cache key. Capital and questionnaire answers do not. Model/report hashes also capture results
and assumptions. Retrieval timestamps remain provenance rather than reproducibility inputs.

## Consequences

Full-universe computation takes minutes; the UI polls stages without fabricated percentages.
The application remains a modular monorepo with no broker or external worker service. This local
single-process deployment is deliberate; horizontal API scaling needs a future job-ownership design.
Internal model cache blobs use Python serialization in the trusted local SQLite file and are not
portable interchange artifacts. Change the explicit model version when numerical semantics change.

Current membership introduces survivorship bias. A stocks-only conservative profile does not protect
capital. Three years describes the estimation window, not the user's investment horizon. Share
purchases, simulations, suitability assessment, taxes, costs and saved portfolios remain out of scope.
