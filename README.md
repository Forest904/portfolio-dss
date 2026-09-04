# Portfolio DSS

Portfolio DSS is an interactive decision support system that helps non-expert investors understand and compare stock portfolios. It makes assumptions, risk, and uncertainty visible; it is not a trading bot or a promise of future performance.

## Week 2 data path

The repository is a modular monorepo containing:

- `apps/api`: Python 3.12, FastAPI, and a framework-independent financial domain;
- `apps/web`: Node.js 24, Next.js App Router, and TypeScript;
- `docs`: product, architecture, data, API, testing, and decision records;
- `data`, `notebooks`, and `scripts`: placeholders for later roadmap work.

The backend now retrieves current S&P 500 constituents from Wikipedia and adjusted daily prices
from Yahoo Finance through replaceable adapters. Normalized source responses are cached in
`data/market_data.sqlite3` for traceability and repeatable valuation snapshots.

Available endpoints:

- `GET /health`;
- `GET /api/v1/universes/sp500`;
- `GET /api/v1/assets/{ticker}`;
- `POST /api/v1/portfolios/valuation`.

Example valuation request:

```json
{
  "positions": [
    {"ticker": "AAPL", "quantity": "10"},
    {"ticker": "MSFT", "quantity": "4.5"}
  ],
  "as_of": "2026-09-04"
}
```

Omit `as_of` to use the latest available completed US session. The response always reports the
actual common valuation date, source provenance, assumptions, and a deterministic snapshot hash.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 24 and npm

## Run locally

Start the API:

```powershell
cd apps/api
uv sync --all-groups
uv run uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; verify it with `GET http://127.0.0.1:8000/health`.

In a second terminal, start the web app:

```powershell
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:3000`. The page checks the API server-side and remains usable when the API is offline. To use another API location, copy `.env.example` to `.env.local` and change `API_BASE_URL`.

## Quality checks

Run backend checks from `apps/api`:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Run frontend checks from `apps/web`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

GitHub Actions runs these commands independently for the backend and frontend using the committed lockfiles.

## Financial defaults

The initial convention is USD, daily adjusted-close prices, daily simple returns, and 252 trading periods per year. Missing values are never imputed silently; series are aligned by timestamp intersection and inadequate data will be reported as an error by the Week 2 data pipeline. S&P 500 comparisons use adjusted SPY prices as an explicitly labelled total-return ETF proxy.

See [`docs/`](docs/) for scope, roadmap, mathematical model, and architecture decisions.

### Market-data settings

The defaults can be changed with `PORTFOLIO_DSS_CACHE_PATH`,
`PORTFOLIO_DSS_PROVIDER_TIMEOUT`, `PORTFOLIO_DSS_PRICE_CACHE_TTL_HOURS`,
`PORTFOLIO_DSS_UNIVERSE_CACHE_TTL_HOURS`, `PORTFOLIO_DSS_STALE_FALLBACK_DAYS`, and
`PORTFOLIO_DSS_MAX_CONSECUTIVE_MISSING`.
