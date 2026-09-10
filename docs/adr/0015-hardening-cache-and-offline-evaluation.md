# ADR 0015 — Range-aware cache and offline evaluation

## Status

Accepted for Week 11.

## Decision

Store normalized Yahoo price series as independently hashed per-asset snapshots. A cached snapshot
may answer a request only when it fully covers the requested interval. The adapter may combine
different assets, preserves request order, uses the oldest contributing retrieval time for freshness,
and hashes the composed response. It does not stitch partial time ranges retrieved at different times,
because revised adjusted prices would make provenance ambiguous.

SQLite uses WAL, a busy timeout, atomic replacement, a covering index, and bounded pruning. Invalid
hashes or payloads are evicted and treated as misses. The legacy exact-request table remains for the
universe cache; old price rows are harmless and need no destructive migration.

Evaluation uses versioned manifests and the checked-in Week 9 snapshot. The application-owned
synthetic demo adapter is explicitly labelled and is never selected by production composition.
Case-study JSON is canonical and HTML is self-contained. Profiling is measurement-only: environment,
inputs, hashes, time, and memory are recorded without flaky CI timing gates.

The efficient-frontier maximum-return endpoint is computed exactly by filling the highest-return
assets up to the configured cap, removing an unnecessary HiGHS call. Singular minimum-variance tie
resolution and SLSQP calls remain deterministic. In-process frontier calculations and native SciPy
entry points are serialized; the supervised guided worker remains isolated in its own process. This
prevents the Windows native access violations reproduced by concurrent API requests.

## Consequences

Asset subsets and contained date ranges reuse data without weakening missing-data policy. Partial
overlaps still fetch a coherent replacement snapshot. A first request after upgrading may be cold.
Offline case studies and the UI demo require no provider, notebook, or cache preparation, but their
selected/synthetic universes must not be presented as full-market evidence.
