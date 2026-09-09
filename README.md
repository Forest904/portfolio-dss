# Portfolio DSS

Portfolio DSS is an interactive decision support system that helps non-expert investors understand and compare stock portfolios. It makes assumptions, risk, and uncertainty visible; it is not a trading bot or a promise of future performance.

## Week 5 efficient frontier and decision alternatives

The repository is a modular monorepo containing:

- `apps/api`: Python 3.12, FastAPI, and a framework-independent financial domain;
- `apps/web`: Node.js 24, Next.js App Router, and TypeScript;
- `docs`: product, architecture, data, API, testing, and decision records;
- `data`, `notebooks`, and `scripts`: placeholders for later roadmap work.

The backend retrieves current S&P 500 constituents from Wikipedia and adjusted daily prices from
Yahoo Finance through replaceable adapters. It now analyzes entered buy-and-hold portfolios against
an equal-dollar buy-and-hold alternative and the SPY total-return proxy on one aligned history
window. Normalized source responses are cached in `data/market_data.sqlite3` for traceability and
repeatable results.

The backend also estimates annualized historical arithmetic returns and sample covariance, then
uses a replaceable SciPy SLSQP adapter to recommend a long-only, fully invested allocation for an
explicit risk-aversion value and optional uniform maximum weight. Solver diagnostics and an
independent constraint check accompany every successful recommendation.

Choose **Compare alternatives** in the web workspace to see the estimated efficient frontier and
switch between conservative, moderate, and aggressive allocations. The profiles target 20%, 50%,
and 80% of the achievable expected-return range. Current holdings, equal weight, and SPY use the
same historical observations for comparison. Allocation changes and numerical decision facts update
locally when switching profiles. **Analyze portfolio** retains the observed historical analysis view.

Available endpoints:

- `GET /health`;
- `GET /api/v1/universes/sp500`;
- `GET /api/v1/assets/{ticker}`;
- `POST /api/v1/portfolios/valuation`;
- `POST /api/v1/portfolios/analyze`;
- `POST /api/v1/portfolios/optimize`;
- `POST /api/v1/portfolios/frontier`.

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

The analysis endpoint accepts the same positions plus an optional `history.start` and
`history.end`. It defaults to the latest three-year window and returns chart-ready performance,
annualized return/volatility, covariance/correlation, holding and sector concentration, benchmark
comparisons, diagnostics, provenance, and a deterministic analysis hash. The web app provides the
corresponding interactive analysis form and progressively disclosed results.

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

Frontier profile defaults can be changed with `PORTFOLIO_DSS_CONSERVATIVE_FRACTION`,
`PORTFOLIO_DSS_MODERATE_FRACTION`, and `PORTFOLIO_DSS_AGGRESSIVE_FRACTION` (defaults: `0.2`, `0.5`,
`0.8`). Values must be finite, strictly increasing, and within `[0, 1]`; invalid settings fail at
startup. The effective mapping and its semantic version appear in each frontier report.

### Monte Carlo uncertainty (Week 7)

Open **Explore uncertainty** under Decision alternatives in either portfolio journey. Compare
1/3/5-year simulated outcomes with fan charts, terminal histograms and loss probabilities; adjust
path count and random seed in advanced controls. Simulations assume continuously maintained
weights and constant parameters, and are not guarantees. See [ADR 0011](docs/adr/0011-monte-carlo-uncertainty.md)
and [validation status](docs/TESTING.md). Desktop/mobile visual acceptance remains pending.
