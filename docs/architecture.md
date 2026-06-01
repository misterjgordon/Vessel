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
├── schema.py          # VesselInputs dataclass — field names for form and upload
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
├── decision_insights/ # Decision-support analytics (Pillar 3)
│   ├── breakeven.py           # breakeven_revenue()
│   ├── sensitivity.py         # sensitivity_analysis()
│   ├── scenario_analysis.py   # scenario_returns(), DEFAULT_SCENARIO_BUNDLES
│   ├── scenario_schedules.py  # scenario_schedules() — per-year cashflows per scenario (Phase 7)
│   └── enrich.py              # enrich() — headline NPV/IRR + insights (View 1)
│
├── config.py          # .env / DATABASE_URL and other environment settings
│
├── db/
│   ├── connection.py  # Engine + session factory; URL from config.get_database_url()
│   ├── models.py      # SQLAlchemy ORM table definitions (see Database section)
│   ├── migrations/    # Alembic migration scripts
│   └── repository.py  # All database reads/writes — no SQL outside this file
│                      # persist_vessel_submission(), save_*, get_*, list_*
│                      # load_teu_medians(), lookup_purchase_price_benchmark()
│                      # domain ↔ ORM mapping for VesselInputs / ValuationResult
│
├── file_parser.py     # CSV / XLSX, XLSM, XLS upload → list[VesselInputs]
│                      # Validates headers match schema; returns parse errors
│
└── excel_reference.py # (existing) Read inputs/outputs from case-study xlsx
```

```
app/
│
├── main.py            # Dash app factory — layout + register callbacks
├── layout.py          # Top-level layout: nav tabs + shared header
├── views/
│   ├── investment.py  # View 1 — input panel, NPV/IRR cards, scenario summary table
│   └── calculation.py # View 2 — schedule table + pivot helpers (presentation only)
└── callbacks.py       # All @app.callback functions — thin wiring only
                       # Rule: zero business logic; zero SQL; zero formulas; no pivot logic
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
│  Fixed Best / Base / Worst (DEFAULT_SCENARIO_BUNDLES) │
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
  Scenario selector: [Inputs | Best | Base | Worst ▾]
  Schedule from scenario_schedules(); pivot/format in calculation.py
```

```
tests/
├── unit/
│   ├── test_case_study_workbook.py   # (existing) golden NPV/IRR contract
│   ├── test_valuation.py             # (existing, unskip after engine done)
│   ├── test_validation.py            # Tier 1 + Tier 2 rule coverage
│   ├── decision_insights/            # breakeven, sensitivity, scenarios, enrich
│   ├── test_file_parser.py           # valid file, wrong headers, dirty data
└── integration/
    └── test_repository.py           # save/load round-trips (SQLite in-memory)
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
[validation.py] validate(raw) → ValidationResult
      │           ├── tier1_errors: list[str]   (block if non-empty)
      │           └── tier2_warnings: list[str] (show but allow proceed)
      │
      ▼ (no tier1 errors)
[schema.py] VesselInputs (typed, clean)
      │
      ▼
[repository.py] save_raw_submission → save_vessel_inputs   ← silver row first
      │           (users can list/load prior inputs from here)
      │
      ▼
[decision_insights/enrich.py] enrich(inputs) → ValuationResult
      │           (base NPV/IRR, breakeven, sensitivity, scenario summaries)
      ▼
[repository.py] save_valuation + save_cashflow_years (base schedule only)
      │           refresh_benchmarks()
      │
      └──► [UI View 1] render headline cards + scenario summary table
```

## Data flow — View 2 (per-year cashflows)

```
User opens Calculation tab (after a successful compute on View 1)
      │
      ▼
[decision_insights/scenario_schedules.py]
      scenario_schedules(inputs) → dict[str, list[CashflowYear]]
      │   Keys: 'Inputs' (form rates) + Best / Base / Worst
      │   (same inflation/discount overrides as scenario_returns)
      ▼
[app/views/calculation.py] pivot schedule → table rows/columns for Dash DataTable
      │
      └──► [UI View 2] user picks scenario in dropdown; table updates
```

Gold `vessel_cashflow_years` stores the **base** schedule from the last persist only.
Scenario schedules are **recomputed on demand** in the app layer (not stored per scenario).

## Data flow — load prior entry (deferred past Phase 7)

```
User selects saved vessel   ← vessel picker UI deferred; repository API ready
      │
      ▼
[repository.py] get_vessel_inputs(id) → VesselInputs
      │           get_valuation(id) → ValuationResult (base cashflow rows)
      │
      └──► [UI] pre-fill form and/or render last computed results
```

## Data flow — file upload (Phase 7 scope)

**Accepted files:** `.csv`, `.xlsx`, `.xlsm`, `.xls` — format is chosen from the
upload filename suffix (see `ACCEPTED_UPLOAD_EXTENSIONS` in `file_parser.py`).

**Required layout (tabular):**

| Part | Rule |
|------|------|
| Row 1 | Header row: `VesselInputs` field names **or** case-study Sample Data labels (`TEU Size`, `Vessel Purchase Price`, …) — mapped via `UPLOAD_HEADER_ALIASES` in `excel_reference.py` |
| Rows 2+ | One vessel per row |
| Excel | `Sample Data for Testing` sheet when present; otherwise first worksheet (`header=0`) |
| Not supported | Vertical “Input & Output (Basic)” layout |

```
User uploads .csv / .xlsx / .xlsm / .xls
      │
      ▼
[file_parser.py] parse_upload(contents, filename)
      │           ├── header check  → header_errors if required columns missing
      │           └── row parse     → one RowResult per data row
      │
      ▼
[validation.py] validate(row) per row → ValidationResult
      │
      ▼
[UI] summary table: one row per vessel
  · green  = passed all checks
  · amber  = tier2 warnings, computable
  · red    = tier1 errors, cannot compute
      │
      ▼
User selects **one** valid row → same pipeline as manual entry
      (validate → persist → enrich → View 1 / View 2)
```

Phase 7 does **not** batch-compute or persist all valid rows at once.

---

## VesselInputs fields

These are the exact header names for **row 1** of an uploaded file and for the UI form.
Each **data row** supplies one vessel; optional extra columns in the file are ignored.

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
| `purchase_date` | `date` | Required — anchors cashflow year labels (Dec 31 each year) |
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
- **IRR:** solved numerically (scipy) on the full series including Year 0.

---

## Database layout (medallion layers)

**One source of truth for field names:** `schema.py` (`VesselInputs`, `CashflowYear`,
`ValuationResult`). ORM column definitions in `db/models.py` mirror those dataclass fields
exactly (snake_case names). `repository.py` maps domain ↔ ORM in both directions — no
parallel field lists in callbacks or views.

**Table prefixes (not PostgreSQL schemas):** Bronze/silver/gold layering is logical only.
Physical tables use prefixes so SQLite (unit/integration tests) and Postgres (dev/prod)
share the same DDL without `CREATE SCHEMA` differences:

| Logical layer | Physical table |
|---------------|----------------|
| Bronze | `raw_vessel_submissions` |
| Silver | `vessel_inputs` |
| Gold | `vessel_valuations`, `vessel_cashflow_years`, `vessel_benchmarks` |

Applying `VesselInputs` to `vessel_inputs` immediately after Tier 1 validation avoids
schema-portability problems: the ORM maps the dataclass to a normal table; there is no
separate `vessel` schema namespace to emulate on SQLite.

**Persist order:** raw submission → **silver `vessel_inputs` row** (as soon as
`VesselInputs` exists) → compute `enrich()` → gold valuation + relational cashflow rows →
refresh benchmarks. Users can list and reload prior silver rows before or without
re-running the engine.

```
Bronze — structural normalisation only; no business rules applied
│
│   Bronze applies minimal structural cleanup at ingest:
│   · Parse file format (CSV/XLSX/XLSM/XLS) into rows
│   · Flag sentinel strings in raw_had_errors (see below)
│   · Standardise null representation across sources
│   Business validity (is the purchase price plausible?) is NOT assessed here.
│   The original payload is always preserved intact in raw_payload.
│
└── raw_vessel_submissions
      id              SERIAL PRIMARY KEY
      submitted_at    TIMESTAMPTZ
      source          TEXT          -- 'manual_form' | 'file_upload'
      filename        TEXT | NULL   -- original upload filename if applicable
      raw_had_errors  BOOLEAN       -- see "raw_had_errors" below
      raw_payload     JSONB         -- exact input as received, unmodified

Silver — validated records (columns = VesselInputs fields)
│
└── vessel_inputs
      id                  SERIAL PRIMARY KEY
      submission_id       FK → raw_vessel_submissions.id
      created_at          TIMESTAMPTZ
      vessel_name         TEXT
      purchase_price      NUMERIC
      vessel_life         INTEGER
      residual_value      NUMERIC
      lw_tonnage          NUMERIC
      revenue_per_day     NUMERIC
      offhire_rate        NUMERIC
      opex_per_day        NUMERIC
      drydock_capex       NUMERIC
      drydock_frequency   INTEGER
      upgrades_capex      NUMERIC
      inflation_rate      NUMERIC
      discount_rate       NUMERIC
      days_of_year        INTEGER
      teu_size            INTEGER
      purchase_date       DATE
      engine_type         TEXT | NULL
      co2_carbon_factor   NUMERIC | NULL

Gold — computed results
│
├── vessel_valuations
│     id                  SERIAL PRIMARY KEY
│     vessel_input_id     FK → vessel_inputs.id
│     computed_at         TIMESTAMPTZ
│     npv                   NUMERIC
│     irr                   NUMERIC | NULL
│     payback_year          INTEGER | NULL
│     investment_signal     TEXT
│     breakeven_rate        NUMERIC | NULL
│     sensitivity           JSONB | NULL   -- [{revenue_per_day, irr}, ...]
│     scenarios             JSONB | NULL   -- {name: {npv, irr, investment_signal}}
│
├── vessel_cashflow_years   -- full schedule; one row per CashflowYear (not JSON)
│     Storage: one row per year (table grows vertically as life increases).
│     Persisted schedule is the **Inputs** (form) scenario only. View 2 scenario
│     schedules are computed via ``scenario_schedules()`` (not stored per scenario).
│     Display pivot (years on Y-axis, cashflow types on X-axis) lives in
│     ``app/views/calculation.py`` — not in callbacks or repository.
│     id                  SERIAL PRIMARY KEY
│     valuation_id        FK → vessel_valuations.id
│     year                  INTEGER
│     period_end            DATE
│     revenue               NUMERIC
│     opex                  NUMERIC
│     drydock_capex         NUMERIC
│     upgrades_capex        NUMERIC
│     free_cashflow         NUMERIC
│     net_cashflow          NUMERIC
│     discounted_cashflow   NUMERIC
│     cumulative_cashflow   NUMERIC
│     UNIQUE (valuation_id, year)
│
└── vessel_benchmarks
      teu_bucket            INTEGER PRIMARY KEY   -- TEU rounded to nearest 1,000
      median_price          NUMERIC
      vessel_count          INTEGER
      last_updated          TIMESTAMPTZ
```

### Key design choices

- `raw_vessel_submissions` is append-only — every submission is preserved exactly as
  received, enabling full audit and reprocessing.
- `vessel_inputs` is the silver record — written **immediately** after Tier 1 passes,
  before NPV/IRR/insights. Linked to the raw submission for traceability. Reloading a saved
  vessel uses `repository.get_vessel_inputs()` → `VesselInputs`.
- `vessel_valuations` + `vessel_cashflow_years` are derived gold — can be recomputed from
  silver inputs; stored for history and audit of the **base** run.
- `vessel_cashflow_years` stores one `CashflowYear` schedule per valuation (the Inputs
  scenario at persist time). View 2 Best/Base/Worst schedules call `scenario_schedules()`.
- `vessel_benchmarks` is a **self-improving gold table**. Seeded from sample data on first
  migration. Rebuilt automatically every time a vessel is saved.
- Tests use **SQLite in-memory** for `make test` and `make test-integration`; no Postgres
  required in CI.
- Defaults and URL behaviour are documented in `config.py` (`get_database_url`,
  `get_migration_database_url`).
- Production: `DATABASE_URL` environment variable. Dev: Docker Compose spins up Postgres
  locally (Phase 8).

### raw_had_errors

Bronze records whether the **incoming payload** contained Excel-style sentinels before
Tier 1 validation, not whether validation failed.

| Who sets it | When |
|-------------|------|
| `repository.save_raw_submission()` | Scans `raw_payload` for sentinel strings (`#VALUE!`, `-`, `N/A`, etc.) using the same sentinel set as `validation.SENTINELS` |

**Why separate from Tier 1 errors:** Tier 1 may coerce or reject sentinels per field;
`raw_had_errors` is an audit flag on the original submission (“this upload was dirty”) for
ops and reprocessing, independent of whether the row eventually validated. Manual form
submissions typically set `raw_had_errors = false` unless the UI passes through dirty
strings.

### TEU benchmark lookup (repository — used by Tier 2 validation)

Implemented in `repository.lookup_purchase_price_benchmark(teu) -> float | None` (Option A:
interpolation lives in the repository, not validation).

1. Round entered TEU to nearest 1,000 → `teu_bucket` (e.g. 7,460 → 7,000; 10,600 → 11,000)
2. Query `vessel_benchmarks` for that exact bucket → return `median_price` if found
3. No exact match → find the two nearest adjacent buckets with data; linearly interpolate
   `median_price`; return the interpolated value
4. Only one neighbour or none → return `None` (validation skips purchase-price check;
   UI may show: "Insufficient TEU data for purchase price validation")

`repository.load_teu_medians() -> dict[int, float]` builds the bucket→median map for
`validate(..., teu_medians=...)`. Batch/file upload may still pass in-batch medians first;
DB medians apply when no batch override.

> **Known gap (Phase 6+):** Revenue-per-day Tier 2 checks still use hardcoded
> `_TEU_REVENUE_SEEDS` in `validation.py`, not the database. Purchase-price benchmarks are
> in scope for Phase 6; revenue benchmarks are flagged for a later phase.

---

## Build sequence

Supporting files (not tied to a single phase): `pyproject.toml`, `uv.lock`, `Makefile`,
`tests/conftest.py`, `src/vessel_valuation/excel_reference.py`,
`tests/unit/test_case_study_workbook.py`.

| Phase | Deliverable | Files to build | Done when |
|-------|-------------|----------------|-----------|
| **1** | Domain schema | `src/vessel_valuation/schema.py` | Importable; field names match [VesselInputs fields](#vesselinputs-fields) |
| **2** | DCF engine | `src/vessel_valuation/model.py`<br>`tests/unit/test_valuation.py` | `make test` green; golden NPV/IRR match Excel basic sheet |
| **3** | Two-tier validation | `src/vessel_valuation/validation.py`<br>`tests/unit/test_validation.py` | `test_validation.py` covers all Tier 1 rules + Tier 2 warnings |
| **4** | Decision insights | `src/vessel_valuation/decision_insights/`<br>`tests/unit/decision_insights/` | decision_insights tests green; `enrich()` returns breakeven, sensitivity, scenarios |
| **5** | File upload parser | `src/vessel_valuation/file_parser.py`<br>`tests/unit/test_file_parser.py` | Parses sample xlsx; flags Sample Vessel #8 (Tier 1); 9/10 rows valid |
| **6** | Persistence layer | `src/vessel_valuation/db/`<br>`alembic.ini`<br>`tests/integration/test_repository.py`<br>`.env.example`<br>`Makefile` `test-integration` | Silver saved before compute; full cashflow rows; benchmark interpolation in repository; `make test-integration` green |
| **7** | Dash UI | `decision_insights/scenario_schedules.py`<br>`app/main.py`<br>`app/layout.py`<br>`app/callbacks.py`<br>`app/views/investment.py`<br>`app/views/calculation.py` | `make run` (or documented env) starts Dash; manual entry or **one** upload row → NPV/IRR on View 1; View 2 shows per-year cashflows for Inputs + Best/Base/Worst |
| **8** | Dev / deploy wiring | `docker-compose.yml`<br>`Dockerfile`<br>`.env.example` (if not done in phase 6)<br>`Makefile` targets: `dev`, `run` | `make dev` starts Postgres + app |
| **9** | Documentation | `docs/writeup.md` (≤ 1 page)<br>`README.md` | README covers `make run`, `make test`, `make dev` |

### Phase detail — file map

**Phase 1 — Schema**

| Path | Role |
|------|------|
| `src/vessel_valuation/schema.py` | `VesselInputs`, `ValuationResult`, `CashflowYear`, `SensitivityPoint`, `ScenarioResult`, `ScenarioBundle`; module constants (`SCRAP_RATE_PER_TONNE`, `SIGNAL_BAND`) |

**Phase 2 — DCF engine**

| Path | Role |
|------|------|
| `src/vessel_valuation/model.py` | `build_schedule`, `calculate_npv`, `calculate_irr`, `investment_signal`, `compute_npv_irr` |
| `tests/unit/test_valuation.py` | Golden NPV/IRR; schedule structure (year 0, drydock years, residual in final year) |

**Phase 3 — Validation**

| Path | Role |
|------|------|
| `src/vessel_valuation/validation.py` | `RawRule` / `InputRule` registries; `validate()`, `tier2_warnings()`; Tier 1 (V-001–V-016) + Tier 2 (W-001+, TEU benchmarks) |
| `tests/unit/test_validation.py` | Sentinels, coercion, residual derivation, TEU price/revenue warnings |

**Phase 4 — Insights**

| Path | Role |
|------|------|
| `src/vessel_valuation/decision_insights/breakeven.py` | `breakeven_revenue` |
| `src/vessel_valuation/decision_insights/sensitivity.py` | `sensitivity_analysis` |
| `src/vessel_valuation/decision_insights/scenario_analysis.py` | `scenario_returns`, `DEFAULT_SCENARIO_BUNDLES` |
| `src/vessel_valuation/decision_insights/enrich.py` | `enrich` |
| `tests/unit/decision_insights/` | Breakeven NPV ≈ 0; sensitivity monotonicity; Best/Base/Worst ordering |

**Phase 5 — File parser**

| Path | Role |
|------|------|
| `src/vessel_valuation/file_parser.py` | `UPLOAD_HEADER_ALIASES` normalisation; `ACCEPTED_UPLOAD_EXTENSIONS`; `parse_dataframe`, `parse_upload`; two-pass validation |
| `tests/unit/test_file_parser.py` | Form + case-study headers, CSV/XLSX bytes, sample workbook (vessel #8 fails Tier 1) |

**Phase 6 — Database**

| Path | Role |
|------|------|
| `src/vessel_valuation/config.py` | `.env` loading; `DATABASE_URL` defaults and getters |
| `src/vessel_valuation/db/connection.py` | Engine + session factory; URL from `config` |
| `src/vessel_valuation/db/models.py` | ORM tables with prefixes; columns mirror `VesselInputs` / `CashflowYear` |
| `src/vessel_valuation/db/repository.py` | Domain ↔ ORM mapping; `persist_vessel_submission` (raw → silver → enrich → gold); `save_raw_submission`, `save_vessel_inputs`, `save_valuation`, `save_cashflow_years`, `get_vessel_inputs`, `get_valuation`, `list_vessels`; `load_teu_medians`, `lookup_purchase_price_benchmark`; `refresh_benchmarks` |
| `src/vessel_valuation/db/migrations/` | Alembic: all prefixed tables + `vessel_benchmarks` seed |
| `alembic.ini` | Alembic project config |
| `tests/integration/test_repository.py` | SQLite in-memory: silver-before-compute, full cashflow round-trip, benchmark lookup |
| `.env.example` | `DATABASE_URL`, app port placeholders |
| `Makefile` | `test-integration` target |

**Phase 7 — Dash app**

| Path | Role |
|------|------|
| `src/vessel_valuation/decision_insights/scenario_schedules.py` | `scenario_schedules(inputs)` → `dict[str, list[CashflowYear]]` for Inputs + `DEFAULT_SCENARIO_BUNDLES`; unit-tested |
| `app/main.py` | App factory; engine/session from `DATABASE_URL`; register callbacks |
| `app/layout.py` | Nav tabs, shared header |
| `app/callbacks.py` | Thin wiring: form/upload → `validate` / `parse_upload` → `persist_vessel_submission` / `enrich` / `scenario_schedules` → components |
| `app/views/investment.py` | View 1: inputs, validation banner, NPV/IRR cards, sensitivity chart, scenario summary (no year table) |
| `app/views/calculation.py` | View 2: scenario dropdown, pivot `list[CashflowYear]` → DataTable columns/rows |

**Phase 7 — out of scope (later):** saved-vessel picker (`list_vessels` UI); user-defined scenario bundles (edit inflation/discount in the UI); batch persist/compute for every valid upload row.

**Phase 7 — local database (Dash must persist across requests):**

- **Tests** (`make test`, `make test-integration`): keep in-memory SQLite via `get_database_url()` default — unchanged.
- **Dash locally:** set `DATABASE_URL=sqlite:///vessel_valuation.db` (same file as Alembic’s default migration URL). Run `alembic upgrade head` once before first launch. Postgres is **not** required for Phase 7; Docker Compose Postgres arrives in Phase 8.
- **App factory:** reads `DATABASE_URL` from the environment; do not rely on the in-memory runtime default when serving the UI.

**Phase 8 — Docker & local dev**

| Path | Role |
|------|------|
| `docker-compose.yml` | Postgres service + app service |
| `Dockerfile` | App image |
| `Makefile` | `make dev`, `make run` (extend existing `test`, `lint`, `format`) |

**Phase 9 — Write-up**

| Path | Role |
|------|------|
| `docs/writeup.md` | ≤ 1 page: approach, assumptions, known gaps |
| `README.md` | Setup, `uv sync`, `make test`, `make dev`, case-study asset paths |
