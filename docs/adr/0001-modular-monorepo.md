# ADR 0001 — Modular Monorepo

- Status: Accepted
- Date: 2026-09-04

## Context

The project needs a Python analytical backend and a Next.js frontend. It should remain easy to extend with new models and data providers, but it is a single-developer three-month academic project.

## Decision

Use one repository containing:

- FastAPI backend;
- Next.js frontend;
- shared documentation;
- experiments/notebooks;
- scripts and tests.

The backend follows domain/application/infrastructure/API dependency boundaries.

Do not use microservices in Phase A/B.

## Consequences

Positive:

- simple local development;
- atomic changes across UI/API/model contracts;
- easier course submission and reproducibility;
- modularity without deployment overhead.

Negative:

- independent service scaling is not a first-class concern;
- discipline is required to preserve module boundaries inside one codebase.
