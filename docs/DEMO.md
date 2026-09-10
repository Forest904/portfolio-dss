# Demonstration Runbook

## Purpose

This runbook defines the supported five-minute interactive demonstration for Portfolio DSS. The
interactive application uses deterministic synthetic prices and clearly labels them as fixture
data. Historical claims come from the separate frozen backtest and case-study reports.

## Prerequisites

- Python 3.12
- `uv`
- Node.js 24 and npm
- Ports 8011 and 3000 available

Run all commands from a clean checkout of the repository.

## Install and start

Terminal 1, from `apps/api`:

```powershell
uv sync --locked --all-groups
uv run uvicorn app.cli.demo:app --host 127.0.0.1 --port 8011
```

Expected checkpoint: Uvicorn reports application startup complete. Opening
`http://127.0.0.1:8011/health` returns status `ok` for `portfolio-dss-api`.

Terminal 2, from `apps/web` in PowerShell:

```powershell
npm ci
$env:API_BASE_URL="http://127.0.0.1:8011"
npm run dev
```

For a POSIX shell:

```bash
npm ci
API_BASE_URL=http://127.0.0.1:8011 npm run dev
```

Open `http://localhost:3000`. Expected checkpoint: the status panel reads **API connected**.

## Fixed five-minute path

### 0:00–0:40 — Establish the boundary

1. Point out the guided builder and the API-connected status.
2. State that this live path uses seeded synthetic data so the interaction is reproducible.
3. State that the frozen historical reports provide the evaluation evidence.

### 0:40–1:25 — Express a preference

Select the moderate answer for all three questions:

- **Balance growth and fluctuations**
- **Somewhat comfortable**
- **Reassess before changing exposure**

Continue to capital, enter `10000`, keep **Historical mean**, and submit the recommendation.

Expected checkpoint: the result identifies the moderate suggestion, USD 10,000 capital, the
eligible synthetic universe, the aligned observation window, and explicit assumptions.

### 1:25–2:40 — Compare alternatives

1. Move between conservative, moderate, and aggressive profiles.
2. Show the efficient-frontier position, estimated annual return, annual volatility, and allocation.
3. Explain that profile switching is local and does not fetch new prices.
4. Open the recommendation reasons and point to the exact facts supporting the summary.

Expected checkpoint: the allocation and metrics change together, while the selected data window and
model remain fixed.

### 2:40–3:30 — Inspect assumptions

Open the advanced evidence area. Point out:

- adjusted-close daily simple returns and 252-period annualization;
- historical arithmetic expected returns and historical sample covariance;
- long-only, fully invested constraints and the maximum weight;
- synthetic provenance and the report hash.

### 3:30–4:35 — Explore uncertainty

Open **Explore uncertainty**. Select a three-year horizon, 10,000 paths, and seed `42`, then run the
simulation.

Expected checkpoint: the result displays the starting USD capital, terminal distribution, fan bands,
histogram, and probability of ending below starting nominal capital. State that the simulation uses
constant parameters and does not guarantee an outcome.

### 4:35–5:00 — Close

Return to the comparison and summarize: the system makes alternatives, assumptions, and uncertainty
visible; the user retains the decision. Mention that transaction costs, taxes, and point-in-time
constituents remain outside Phase B.

## Historical evidence and fallback

If the live application cannot run, open these self-contained files directly in a browser:

1. `examples/case-studies/week11/report/report.html` for the three DSS case studies.
2. `examples/backtest/week9/report/report.html` for the six-strategy walk-forward comparison.

The reports contain no external assets or API calls. Their adjacent JSON files provide full-precision
values, configuration, provenance, assumptions, and stable hashes.

If time permits after the live path, use the backtest report to emphasize that the selected sample
does not identify one universally superior estimator.

## Troubleshooting

- **API offline in the UI:** confirm terminal 1 is still running and that terminal 2 set
  `API_BASE_URL` before starting Next.js.
- **Port already in use:** stop the process using 8011 or 3000. Keep the documented ports for the
  prepared demo rather than changing URLs during the presentation.
- **Stale web process:** stop Next.js with `Ctrl+C`, set `API_BASE_URL` again, and restart it.
- **Guided job does not complete:** refresh once. If the problem remains, switch immediately to the
  static case-study report.
- **Provider error:** verify that `app.cli.demo:app`, not `app.main:app`, started on port 8011. The
  offline composition never calls Wikipedia or Yahoo Finance.

## Cleanup

Stop both development servers with `Ctrl+C`. The offline API stores its temporary SQLite files under
the operating system temporary directory in `portfolio-dss-offline-demo`; it does not use the
production cache under `data/`.
