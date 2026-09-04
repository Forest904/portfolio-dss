# ADR 0005 — Development Toolchain and CI

- Status: Accepted
- Date: 2026-09-04

## Context

The modular monorepo needs reproducible setup and automated checks for both Python and TypeScript without adding deployment or service-management complexity.

## Decision

- Manage the Python 3.12 backend with uv and a committed `uv.lock`.
- Check Python with Ruff, mypy, and pytest.
- Manage the Node.js 24 frontend with npm and a committed `package-lock.json`.
- Check the frontend with ESLint, TypeScript, Vitest, and a production Next.js build.
- Run backend and frontend jobs independently in GitHub Actions.

## Consequences

Positive:

- local and CI environments use the same locked dependency graphs;
- independent jobs provide fast, focused failures;
- linting, typing, tests, and build viability are enforced from the first implementation week.

Negative:

- contributors must install both uv and the selected Node.js major version;
- two ecosystem lockfiles and toolchains must be maintained.
