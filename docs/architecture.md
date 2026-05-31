# Architecture

Vessel Valuation Tool — structural overview.

---

## Guiding principles

1. **Three pillars, three layers.** Every feature maps to one of the three product pillars
   (Input → Calculate → Insights) and one of three code layers (UI → logic → data).
   Mixing layers is a red flag.
2. **One source of truth per concern.** Field names live in the dataclass. Business rules
   live in validation. Formulas live in the engine. The UI only calls, never computes.
3. **Tests anchor the engine to Excel.** The golden NPV/IRR values from the reference
   workbook are locked in pytest. New logic must not break them.

---

## Pillar map

```
┌─────────────────────────────────────────────────────────┐
│  PILLAR 1 · INPUT          PILLAR 2 · CALCULATE         │
│  ─────────────────         ────────────────────         │
│  Manual entry form    ──►  VesselInputs dataclass       │
│  File upload          ──►  (validated)           ──►    │
│  Load saved record    ──►                               │
│                                                         │
│                            DCF engine                   │
│                            · build_cashflows()          │
│                            · calculate_npv()            │
│                            · calculate_irr()            │
│                                                         │
│  PILLAR 3 · INSIGHTS                                    │
│  ───────────────────                                    │
│  · breakeven_revenue_per_day()                          │
│  · sensitivity_irr_by_revenue()                         │
│  · scenario_returns()         (Best / Base / Worst)     │
└─────────────────────────────────────────────────────────┘
```

---

## Module layout

```
src/vessel_valuation/
│
├── schema.py          # VesselInputs dataclass — canonical field names
│                      # ValuationResult — computed NPV, IRR, cashflows
│
├── validation.py      # Two-tier validation (see D-004)
│                      # Tier 1: type / structural errors  → blocks compute
│                      # Tier 2: business-rule warnings    → advisory only
│
├── model.py           # DCF engine (pure functions, no UI imports)
│                      # build_cashflows(), calculate_npv(), calculate_irr()
│                      # compute_npv_irr()  ← entry point for the UI
│
├── insights.py        # Decision-support analytics
│                      # breakeven_revenue_per_day()
│                      # sensitivity_irr_by_revenue()
│                      # scenario_returns()
│
├── db/
│   ├── connection.py  # Engine + session factory; reads DATABASE_URL from env
│   ├── models.py      # SQLAlchemy ORM table definitions (see Database section)
│   ├── migrations/    # Alembic migration scripts
│   └── repository.py  # All database reads/writes — no SQL outside this file
│                      # save_raw_submission(), save_vessel_inputs()
│                      # save_valuation(), list_vessels(), get_valuation()
│
├── file_parser.py     # CSV / XLSX, XLSM, XLS upload → list[VesselInputs]
│                      # Validates headers match schema; returns parse errors
│
└── excel_reference.py # (existing) Read inputs/outputs from case-study xlsx
```

```
app/
│
├── app.py             # Dash app factory — layout + register callbacks
├── layout.py          # Top-level layout: nav tabs + shared header
├── views/
│   ├── investment.py  # View 1 — input panel, NPV/IRR cards, scenario table
│   └── calculation.py # View 2 — year-by-year cash flow table (replicates Excel sheet)
└── callbacks.py       # All @app.callback functions — thin wiring only
                       # Rule: zero business logic; zero SQL; zero formulas
```

### View 1 — Investment Summary
```
┌─ Inputs ──────────────────────────────────────────────┐
│  Manual fields  OR  File upload                        │
│  [Validation banner: errors in red / warnings amber]  │
└───────────────────────────────────────────────────────┘
┌─ Results ─────────────────────────────────────────────┐
│  NPV: $X,XXX,XXX     IRR: XX.X%                       │
│  Break-even revenue: $XX,XXX/day                      │
└───────────────────────────────────────────────────────┘
┌─ Sensitivity ─────────────────────────────────────────┐
│  IRR vs Revenue per Day (line chart, $1k steps)       │
│  [Min ___] [Max ___]  ← user-defined range            │
└───────────────────────────────────────────────────────┘
┌─ Scenarios ───────────────────────────────────────────┐
│  [+ Add / Edit Scenarios]                             │
│                                                        │
│            Best    Base    Worst                       │
│  Inflation   1%     3%      5%                         │
│  Disc. Rate  8%    10%     12%                         │
│  ─────────────────────────────                         │
│  NPV       $X.Xm  $X.Xm   $X.Xm                      │
│  IRR       X.X%   X.X%    X.X%                        │
└───────────────────────────────────────────────────────┘
```

### View 2 — Calculation Detail
```
┌─ Year-by-Year Cash Flow ──────────────────────────────┐
│  Year │ Revenue │ OpEx │ Drydock │ Upgrades │ FCF │ DCF│
│     1 │  17,885k│  3,760k│       0 │     515k │ ... │ ..│
│     2 │  17,885k│  3,872k│       0 │     530k │ ... │ ..│
│   ... │       ..│      ..│      .. │       .. │ ... │ ..│
│    25 │  17,885k│  7,642k│       0 │    1,047k│ ... │ ..│
└───────────────────────────────────────────────────────┘
  Scenario selector: [Best ▾]  applies scenario to all rows
```

```
tests/
├── unit/
│   ├── test_case_study_workbook.py   # (existing) golden NPV/IRR contract
│   ├── test_valuation.py             # (existing, unskip after engine done)
│   ├── test_validation.py            # Tier 1 + Tier 2 rule coverage
│   ├── test_insights.py              # breakeven, sensitivity, scenarios
│   ├── test_file_parser.py           # valid file, wrong headers, dirty data
│   └── test_repository.py           # save/load round-trips (SQLite in tests)
└── conftest.py                       # (existing) fixtures
```

---

## Data flow — manual entry

```
User fills form
      │
      ▼
[UI] form values (raw strings / numbers)
      │
      ▼
[validation.py] validate_inputs(raw) → ValidationResult
      │           ├── tier1_errors: list[str]   (block if non-empty)
      │           └── tier2_warnings: list[str] (show but allow proceed)
      │
      ▼ (no tier1 errors)
[schema.py] VesselInputs (typed, clean)
      │
      ▼
[model.py] compute_npv_irr(inputs) → {npv, irr, cashflows}
      │
      ├──► [insights.py] breakeven, sensitivity, scenarios
      │
      └──► [UI] render outputs + charts
```

## Data flow — file upload

```
User uploads CSV / XLSX / XLSM / XLS
      │
      ▼
[file_parser.py] parse_upload(contents, filename)
      │           ├── header check  → ParseError if mismatch
      │           └── row parse     → list[raw_dict]
      │
      ▼
[validation.py] validate_inputs(row) per row → ValidationResult
      │
      ▼
UI renders a table: one row per vessel
  · green  = passed all checks
  · amber  = tier2 warnings, computable
  · red    = tier1 errors, cannot compute
```

---

## VesselInputs fields (canonical)

These are the exact header names expected in uploaded files and used in the UI form.

| Field | Type | Notes |
|-------|------|-------|
| `vessel_name` | `str` | Free text label |
| `purchase_price` | `float` | USD, Year 0 outflow |
| `vessel_life` | `int` | Years of active operation |
| `residual_value` | `float` | Proceeds at end of Year T |
| `revenue_per_day` | `float` | Contracted daily charter rate |
| `offhire_rate` | `float` | Decimal (e.g. 0.02 = 2%) |
| `opex_per_day` | `float` | Operating expense, before inflation |
| `drydock_capex` | `float` | Cost per drydock event |
| `drydock_frequency` | `int` | Years between drydocks (default 5) |
| `upgrades_capex` | `float` | Annual upgrades cost, before inflation |
| `inflation_rate` | `float` | Applied to OpEx + CapEx only |
| `discount_rate` | `float` | Hurdle rate for NPV/IRR |

Required validation + derivation fields:

| Field | Type | Notes |
|-------|------|-------|
| `teu_size` | `int` | Required — drives Tier 2 purchase price and revenue checks |
| `lw_tonnage` | `float` | Required — source for residual value derivation (`lw_tonnage × 400.0`) |
| `days_of_year` | `int` | Required — must equal 365; validated at Tier 1 |

Optional metadata (stored, not computed):

| Field | Type | Notes |
|-------|------|-------|
| `purchase_date` | `date \| None` | Aligns cashflow year labels |
| `engine_type` | `str \| None` | Metadata only |
| `co2_carbon_factor` | `float \| None` | Metadata only |

---

## Validation rule registry

Two-stage flow — raw dicts never reach the engine. `VesselInputs` only exists after Tier 1 fully passes.

```
raw dict (strings / numbers from form or file)
    │
    ▼  Tier 1 checks + type coercion
    │  → any error: return list[str] errors, stop here
    ▼
VesselInputs (typed dataclass)
    │  residual_value resolved here if missing: lw_tonnage × 400.0
    ▼
    │  Tier 2 business-rule checks on typed fields
    │  → collect list[str] warnings, user may proceed
    ▼
engine / persistence
```

Each rule is a typed `ValidationRule` object. Adding a rule = appending one item to the list.

```
ValidationRule(
    code     = "V-001",          # unique identifier
    tier     = 1,                # 1 = error (blocks), 2 = warning (advisory)
    message  = "...",            # shown verbatim in the UI
    check    = lambda v: ...     # Tier 1: (raw_dict) -> bool
                                 # Tier 2: (VesselInputs) -> bool
)
```

New rules are added incrementally as data patterns are discovered — no structural changes required.

---

## Validation rules (Tier 1 — errors, block coercion to VesselInputs)

| Rule | Condition |
|------|-----------|
| Required fields present | All required fields must be non-empty |
| No sentinel strings | `#VALUE!`, `-`, `N/A`, empty string in any numeric field → error |
| Numeric fields coercible | All numeric fields must convert to correct Python type |
| Positive life | `vessel_life >= 1` |
| Rates in range | `0 <= offhire_rate < 1`, `0 < discount_rate < 1`, `0 <= inflation_rate < 1` |
| Cost fields positive | `purchase_price`, `opex_per_day`, `drydock_capex`, `upgrades_capex` > 0 |
| Days of year | `days_of_year == 365` — model supports no other value |
| LWT present | `lw_tonnage` must be numeric (used to derive residual if not provided directly) |

## Residual value resolution (after Tier 1, before Tier 2)

If `residual_value` is provided → use it directly.
If `residual_value` is missing or null → compute `lw_tonnage × SCRAP_RATE_PER_TONNE` where `SCRAP_RATE_PER_TONNE = 400.0` (constant derived from sample data: all vessels divide to exactly $400/LT).

## Validation rules (Tier 2 — warnings, run on VesselInputs)

| Rule | Condition | Basis |
|------|-----------|-------|
| Purchase price vs TEU-class median | Outside ±10% of TEU-class median in current batch/DB | D-014 |
| Residual >= Purchase | `residual_value >= purchase_price` — likely data error | Business logic |
| Revenue below OpEx | `revenue_per_day × (1 − offhire_rate) < opex_per_day` — vessel loses money daily | Margin logic |
| Revenue vs TEU-class range | More than $5,000 outside TEU-class expected range | D-009 |

> Tier 2 thresholds are stubs — refineable without structural changes.

---

## DCF calculation conventions

Matching the reference Excel workbook (see `test_case_study_workbook.py`):

- **Year 0:** purchase price as a negative cash flow, on Dec 31 of purchase year.
- **Years 1 – T:** annual free cash flow = Revenue − OpEx − CapEx, end of each year.
- **Year T only:** add `residual_value` to the final year cash flow.
- **Inflation:** factor `(1 + inflation_rate) ^ t` applied to OpEx and CapEx from year 1.
  Revenue is fixed (time-charter contract assumption).
- **Drydock:** occurs in years that are multiples of `drydock_frequency`
  (e.g. years 5, 10, 15, 20 for a 25-year life and frequency 5).
  Year 25 itself is not a drydock year under the reference model.
- **NPV formula:** `sum(cf_t / (1 + r)^t for t in 0..T)` — this is equivalent to
  Excel's `NPV(r, cf1..cfT) × (1 + r) + cf0`.
- **IRR:** solved numerically (scipy or numpy-financial) on the full series including Year 0.

---

## Database layout (medallion layers)

The database uses two PostgreSQL schemas. Function and column names are business-domain vocabulary — not layer names.

```
raw schema  (Bronze layer — structural normalisation only; no business rules applied)
│
│   Bronze applies minimal structural cleanup at ingest:
│   · Parse file format (CSV/XLSX/XLSM/XLS) into rows
│   · Convert sentinel strings (#VALUE!, -, N/A) to null; flag raw_had_errors
│   · Standardise null representation across sources
│   Business validity (is the purchase price plausible?) is NOT assessed here.
│   The original payload is always preserved intact in raw_payload.
│
└── raw.vessel_submissions
      id              SERIAL PRIMARY KEY
      submitted_at    TIMESTAMPTZ
      source          TEXT          -- 'manual_form' | 'file_upload'
      filename        TEXT | NULL   -- original upload filename if applicable
      raw_had_errors  BOOLEAN       -- true if any sentinel strings were found
      raw_payload     JSONB         -- exact input as received, unmodified

vessel schema  (Silver layer — validated canonical records)
│
├── vessel.inputs
│     id              SERIAL PRIMARY KEY
│     submission_id   FK → raw.vessel_submissions.id
│     created_at      TIMESTAMPTZ
│     vessel_name     TEXT
│     purchase_price  NUMERIC
│     vessel_life     INTEGER
│     residual_value  NUMERIC
│     revenue_per_day NUMERIC
│     offhire_rate    NUMERIC
│     opex_per_day    NUMERIC
│     drydock_capex   NUMERIC
│     drydock_freq    INTEGER
│     upgrades_capex  NUMERIC
│     inflation_rate  NUMERIC
│     discount_rate   NUMERIC
│     teu_size        INTEGER | NULL
│     purchase_date   DATE | NULL
│     engine_type     TEXT | NULL
│
└── vessel.valuations  (Gold layer — computed results)
      id              SERIAL PRIMARY KEY
      vessel_input_id FK → vessel.inputs.id
      computed_at     TIMESTAMPTZ
      npv             NUMERIC
      irr             NUMERIC
      cashflows       JSONB         -- list of annual net cash flows
      breakeven_rate  NUMERIC | NULL
      sensitivity     JSONB | NULL  -- [{revenue_per_day, irr}, ...]
      scenarios       JSONB | NULL  -- {best, base, worst} → {npv, irr}
```

└── vessel.benchmarks  (Gold layer — TEU-class purchase price benchmarks)
      teu_bucket        INTEGER PRIMARY KEY   -- TEU rounded to nearest 500
      median_price      NUMERIC               -- median purchase price for this bucket
      vessel_count      INTEGER               -- vessels contributing to this median
      last_updated      TIMESTAMPTZ
```

### Key design choices
- `raw.vessel_submissions` is append-only — every submission is preserved exactly as received, enabling full audit and reprocessing.
- `vessel.inputs` is the silver record — clean, typed, validated. Linked back to the raw submission so you can always trace where a record came from.
- `vessel.valuations` is derived — can be recomputed from `vessel.inputs` at any time. Stored for history and fast retrieval.
- `vessel.benchmarks` is a **self-improving gold table**. Seeded from sample data on first migration. Rebuilt automatically every time a vessel is saved. TEU coverage improves as the fleet registry grows.
- Tests use **SQLite in-memory** so no Postgres is required to run `make test`.
- Production: `DATABASE_URL` environment variable. Dev: Docker Compose spins up Postgres locally.

### TEU benchmark lookup (used by Tier 2 validation)

1. Round entered TEU to nearest 500 → `teu_bucket` (e.g. 9,200 → 9,000; 9,400 → 9,500)
2. Query `vessel.benchmarks` for that exact bucket
3. Exact match found → compare `purchase_price` against `median_price ± 10%`
4. No exact match → find the two nearest adjacent buckets that have data; linearly interpolate `median_price`; apply ± 10% to the result
5. Only one neighbour or none → skip the check entirely; show info notice: "Insufficient TEU data for purchase price validation"

---

## Build sequence

| Phase | Deliverable | Done when |
|-------|-------------|-----------|
| 1 | `schema.py` — VesselInputs + ValuationResult dataclasses | Importable, field names match table above |
| 2 | `model.py` — DCF engine | `make test` green (golden NPV/IRR match) |
| 3 | `validation.py` — two-tier rules | `test_validation.py` covers all Tier 1 rules |
| 4 | `insights.py` — breakeven, sensitivity, scenarios | `test_insights.py` green |
| 5 | `file_parser.py` — upload handler | Parses sample xlsx cleanly; flags Vessel #8 |
| 6 | `db/` — ORM models + repository | save/load round-trip passes with SQLite |
| 7 | `app/` — Dash UI | App runs; inputs → outputs → insights render |
| 8 | Docker Compose + env config | `make dev` starts Postgres + app |
| 9 | Write-up + README | ≤ 1 page; README covers `make run` + `make test` |
