# Vessel Valuation Tool — Write-up

## Approach

Single-vessel DCF model aligned to the case-study Excel workbook: Year 0 purchase, annual operating cash flows with inflation on costs only, drydock on a fixed frequency, residual in the final year. The Python engine is covered by golden NPV/IRR tests against the reference file.

Inputs arrive via manual form or tabular upload (CSV/Excel). Two-tier validation separates blocking data errors (Tier 1) from advisory business rules (Tier 2). Valid runs persist to SQLite/Postgres through a bronze → silver → gold path; the Dash UI calls validation, `enrich()`, and the repository only—no formulas in the app layer.

## Insights for investment decisions

- Headline NPV, IRR, and invest / marginal / do-not-invest signal vs discount hurdle
- Breakeven revenue per day and undiscounted payback year
- IRR sensitivity to charter rate
- Best / Base / Worst macro scenarios (paired inflation and discount bundles)
- Compare tab: overlay free cash flow for any two **saved** database entries

## Known gaps

- **Upload does not auto-save** — each vessel requires **Calculate valuation** then **Save to database**; Compare and Saved vessels lists read the database only.
- **No fleet screening table** — multi-row uploads are validated in bulk but not ranked or batch-persisted.
- **TEU benchmarks** are seeded / fleet-derived stubs; not live market data.
- **Scenario bundles** are fixed defaults; not editable in the UI.
- **No export** (PDF/Excel) for board packs.
- **Shared URL for staff** — `make dev` is localhost-only; hosting/tunnel/deploy is a follow-on step.

## Assumptions

See [assumptions.md](assumptions.md) for timing, inflation, drydock, and validation thresholds.
