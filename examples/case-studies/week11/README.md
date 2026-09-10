# Week 11 reproducible case studies

These three cases reuse the frozen Week 9 price snapshot. They require no provider calls, cache
priming, notebook execution, or manual data transformation.

From `apps/api`, run:

```powershell
uv run python -m app.cli.case_studies --manifest ../../examples/case-studies/week11/manifest.json --snapshot ../../examples/backtest/week9/snapshot.json --output ../../output/week11-cases
```

The command writes canonical `report.json` and a self-contained `report.html`. The cases illustrate
a concentrated existing portfolio, relative guided risk profiles over a selected five-stock subset,
and sensitivity to the expected-return estimator. They are deliberately selected educational
examples, not evidence that the basket represents the full S&P 500 or that one model will outperform.

See [`docs/LIMITATIONS.md`](../../../docs/LIMITATIONS.md) before interpreting the results.
