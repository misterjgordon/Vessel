# Handoff summary

**Date:** 2026-06-02  
**Branch:** `main` (local changes not committed)

---

## What this session covered

1. **Seaspan-style finance Q&A** — Mapped likely stakeholder questions to actual model behaviour (timing, flat TC revenue, no tax/debt/early exit, validation stubs, etc.).
2. **Clarified model definitions** — Confirmed breakeven is **gross** `revenue_per_day` (pre-off-hire); inflation hits OpEx/CapEx only; scenario defaults use Fisher-style paired rates.
3. **Documentation** — Extended `docs/assumptions.md` with explicit bullets (see below). No engine or UI code changes in this session.

---

## Documentation updates (`docs/assumptions.md`)

| Section | Added / clarified |
|--------|-------------------|
| **Revenue** | Inflation escalates costs only; fixed time-charter rate. |
| **Breakeven charter rate** (new) | Gross $/day at NPV = 0; off-hire still applied in cashflows; uses base discount rate. |
| **Scenario analysis** | Default discount 8% / 10% / 12% with inflation 1% / 3% / 5%; **2%** real hurdle held across scenarios; **7 pp** nominal (discount − inflation) gap from case-study test data; Base = golden-test pair. |

**Source of truth for finance assumptions:** `docs/assumptions.md`  
**Architecture / decisions:** `docs/architecture.md`, `docs/decisions.md`

---

## Finance logic — quick reference for demos

| Topic | Behaviour |
|-------|-----------|
| **Cashflow timing** | End-of-year (Dec 31); purchase at year 0; residual at year T only. |
| **Revenue** | Fixed gross rate; effective = `revenue_per_day × (1 − offhire_rate)`; owner bears OpEx/CapEx (time-charter, not bareboat). |
| **Inflation** | Compounds on OpEx and CapEx from year 1; **not** on revenue. |
| **Breakeven** | Solves gross `revenue_per_day` where NPV = 0 (`decision_insights/breakeven.py`). |
| **NPV / IRR** | `src/vessel_valuation/dcf.py`; IRR via `scipy.optimize.brentq` (returns `None` if no solution). |
| **Investment signal** | FAVORABLE / MARGINAL / UNFAVORABLE vs discount ± `SIGNAL_BAND` (2%). |
| **Scenarios** | `DEFAULT_SCENARIO_BUNDLES` in `scenario_analysis.py`; user can override; warnings in `scenario_bundles.py`. |
| **Out of scope** | Tax, debt, FX, early sale, index-linked charters, ESG in DCF (`co2_carbon_factor` stored only). |

---

## In-flight work (uncommitted on disk)

Beyond `docs/assumptions.md`, the working tree includes changes not part of this doc session:

- `app/callbacks/` (`_helpers.py`, `compute.py`, `persistence.py`)
- `app/views/investment.py`, `form_defaults.py`, `component_ids.py`
- `src/vessel_valuation/dcf.py`, `db/repository.py`, `decision_insights/enrich.py`, `scenario_analysis.py`
- Tests: `test_dcf.py`, `test__helpers.py`, new `test_purchase_price_scenarios.py`
- Local `vessel_valuation.db` modified (typically gitignored or local-only)

**Before merge:** run `make test` and `make lint`; review purchase-price scenario work end-to-end.

---

## Known doc / code nuance

- **Scenario “spread” wording:** `docs/assumptions.md` now distinguishes **2% real** hurdle (design intent) vs **7 pp nominal** gap (discount − inflation in default bundles). `scenario_bundles.py` warning text still refers to a “constant 2% spread” while checking `discount_rate - inflation_rate` (7 pp for defaults)—consider aligning message with assumptions if that confuses users.

---

## Suggested follow-ups

1. **UI labels** — Optional: breakeven card “Breakeven (gross $/day)” to match assumptions.
2. **Seaspan prep** — One-page walkthrough: golden Excel case → same inputs in app → assumptions doc.
3. **Calibrate stubs** — PP÷TEU ±10%, revenue anchors, `vessel_benchmarks` from real fleet data (see D-009, D-014, D-020 in `docs/decisions.md`).
4. **Commit** — Stage `docs/assumptions.md` (and related code) when the feature branch is ready; do not commit `vessel_valuation.db` unless intentional.

---

## Run / test

```bash
./run.sh                    # http://localhost:8050
make test
make lint
```

Golden NPV/IRR: `tests/unit/vessel_valuation/test_excel_reference.py`
