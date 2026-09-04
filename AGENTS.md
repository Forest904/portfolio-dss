# AGENTS.md

This file defines the working rules for coding agents and contributors in this repository.

## Product principle

Portfolio DSS is a **Decision Support System**, not a trading bot and not a price-prediction product. Every implementation decision should improve one or more of these goals:

1. help a non-expert understand a portfolio;
2. expose the trade-off between return, risk, and uncertainty;
3. compare meaningful alternatives;
4. explain recommendations;
5. keep models modular so future signals can be integrated without rewriting the optimizer.

## Architecture rules

- Keep domain logic independent from FastAPI, Next.js, databases, and market-data libraries.
- Depend on interfaces/protocols at domain/application boundaries.
- External services are adapters, not domain dependencies.
- The optimizer must consume model outputs through stable contracts. It must not know whether expected returns came from historical data, a forecast model, or future sentiment analysis.
- Avoid premature microservices. Start as a modular monorepo with one API and one web application.
- Prefer explicit, typed DTOs and domain objects over unstructured dictionaries.
- Keep calculations deterministic when a random seed is supplied.
- Keep time horizon, annualization convention, price field, and return convention explicit.
- Do not silently fill missing market data.
- Do not mix exploratory notebook code with production application code.

## Python rules

- Python 3.12+.
- Use type hints for public functions.
- Prefer small pure functions for financial calculations.
- Use `Protocol` or abstract base classes for replaceable model/provider contracts.
- Use Pydantic only at API/configuration boundaries; domain logic should not depend on Pydantic.
- Add tests for numerical invariants and edge cases.

## Frontend rules

- Next.js + TypeScript.
- Organize UI by product feature rather than by generic component type when possible.
- Financial values must always display units and time horizons.
- Charts must have readable labels and must not imply certainty where only simulations or estimates exist.
- Advanced mathematical details should be available without blocking the simple user flow.

## Decision-support rules

- Recommendations must include their assumptions.
- Always distinguish observed historical values, estimated parameters, forecasts, and simulated outcomes.
- Never present a forecast as a guaranteed future value.
- Current portfolio, optimized portfolio, S&P 500 benchmark, and equal-weight benchmark must use comparable time windows and conventions.
- Explanations should initially be deterministic and traceable to model outputs.

## Scope discipline

Phase B is the target release. Phase C features must not block Phase B.

Before adding a feature, check `docs/SCOPE.md` and `docs/ROADMAP.md`.

When an architectural decision changes, add or update an ADR in `docs/adr/`.
