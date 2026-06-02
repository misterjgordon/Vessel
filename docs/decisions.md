# Project Decisions Log

Tracks key architectural, technical, and product decisions made throughout the build.
Each entry records what was decided, why, and any trade-offs acknowledged.

---

## D-001 · UI Framework: Dash

**Decision:** Use Plotly Dash as the application framework.
**Reason:** Dash produces a browser-based web app written entirely in Python — no JavaScript required. The tool needs to feel like a seamless web application rather than a script or spreadsheet. Seaspan explicitly lists Dash as the preferred delivery format in the case study brief.
**Trade-offs:** Jupyter Notebook would be faster to sketch, but is not web-app-ready and requires a running kernel. Dash is deployable as a standard web service.

---

## D-002 · Input Method: Manual Form + File Upload

**Decision:** Support two input paths — a manual entry form for a single vessel, and a file upload (CSV or XLSX) for bulk entry. Both paths feed the same validated data structure.
**Reason:** Manual entry covers the demo and single-investment use case. File upload lets the app handle the 10-vessel sample sheet and mirrors how BI teams actually work (spreadsheet hand-offs).
**Trade-offs:** Adds upload parsing complexity. Mitigated by requiring headers to exactly match the defined `VesselInputs` data class fields (or case-study display aliases). Invalid files are rejected early with a clear error message.

---

## D-003 · Data Model: Typed Dataclass for Vessel Inputs

**Decision:** All vessel inputs are represented by a single Python `dataclass` (`VesselInputs` in `schema.py`). Field names are shared by the UI form and file upload header row.
**Reason:** A single source of truth for field names prevents drift between the form, the file parser, the validation layer, and the calculation engine. Downstream code only ever receives a validated `VesselInputs` instance.
**Trade-offs:** Adds a mapping step from raw Excel/CSV column names to dataclass fields. Acceptable given the small fixed field count.

---

## D-004 · Validation: Two-Tier Warning/Error System

**Decision:** Validation runs in two tiers. Tier 1 (errors): type or structural problems that prevent calculation — e.g. non-numeric purchase price, missing required field, `#VALUE!` literal. Tier 2 (warnings): values are valid types but fail a business-rule check — e.g. purchase-price÷TEU ratio outside the TEU-class band, residual value exceeds purchase price. The UI blocks calculation on Tier 1 errors; it shows warnings for Tier 2 but allows the user to proceed.
**Reason:** Directly motivated by the dirty data in Sample Vessel #8 (purchase price $9M vs. ~$90M pattern, `#VALUE!` residual). Separating hard errors from soft warnings gives the user actionable feedback without being unnecessarily blocking.
**Implementation:** `src/vessel_valuation/validation/` — `structural_rules.py` (Tier 1 registry), `business_rules.py` (Tier 2 registry), `coercion.py`, and `validate()` in `__init__.py`. UI and engine import from this package only.

---

## D-005 · Persistence: SQLAlchemy + Alembic, SQLite Prototype

**Decision:** Persist submissions and results through SQLAlchemy ORM and Alembic migrations. The prototype ships on **SQLite** (in-memory for tests/scripts; file `vessel_valuation.db` for the Dash app). Production targets **PostgreSQL** via `DATABASE_URL` — same DDL, no second codebase path.
**Reason:** The 10-vessel sample set is seed data for a fleet registry, not a throwaway test fixture. The tool is explicitly meant to scale. A real persistence story with versioned schema changes is required for auditability and fleet growth.
**Trade-offs:** SQLite limits concurrent writers; acceptable for local demo and CI. Production adds connection pooling, managed Postgres, and row-level auth (e.g. Django REST) without changing valuation logic.

---

## D-006 · Database Layout: Medallion Layers via Table Prefixes

**Decision:** Bronze / silver / gold layering is **logical only**. Physical tables use prefixes so SQLite (tests, prototype) and PostgreSQL (production) share the same DDL without `CREATE SCHEMA` differences. Python code uses business vocabulary — not bronze/silver/gold in identifiers.

| Layer concept | Physical table(s) | What it holds |
|---|---|---|
| Bronze | `raw_vessel_submissions` | Every submission exactly as received (`raw_payload` JSON) |
| Silver | `vessel_inputs` | Validated, normalised `VesselInputs` (one row per vessel) |
| Gold | `vessel_valuations`, `vessel_cashflow_years`, `vessel_benchmarks` | Computed NPV/IRR, per-year schedules, TEU-bucket median purchase prices |

**Reason:** No raw data is ever lost; audit trail from submission → validation → computation; re-run gold without re-ingesting bronze. Prefix-based tables avoid SQLite vs Postgres schema portability problems.

---

## D-007 · UI/Engine Separation

**Decision:** Dash callback functions contain zero business logic. Every callback's job is exactly: collect inputs → call a function from `dcf.py`, `decision_insights/`, `validation`, or `db/repository.py` → pass the result to a Dash component. No formulas, no data transforms, no SQL in callbacks.
**Reason:** Makes the entire engine independently testable without a running browser. The same `compute_npv_irr()` that the UI calls is what `make test` exercises. Swapping Dash for an API or notebook later requires no changes to any logic module.

---

## D-008 · IRR Solver: scipy.optimize.brentq

**Decision:** Use `scipy.optimize.brentq` for the IRR calculation (also used for breakeven charter rate in `decision_insights/breakeven.py`).
**Reason:** `numpy-financial`'s `npf.irr()` returns `NaN` silently when cash flows produce multiple sign changes or no real solution — the caller receives a meaningless number with no indication of failure. A parameter change (e.g. large inflation-adjusted drydock CapEx overwhelming revenue in a given year) could produce mid-life negative cash flows depending on user assumptions. `scipy.optimize.brentq` defines an explicit search bracket, raises a clear exception if no solution exists, and is fully controllable. Failures surface as errors in the UI rather than silent wrong answers.
**Trade-offs:** Requires choosing a bracket (e.g. −99% to +999% for IRR). The bracket is wide enough to cover all realistic vessel IRRs. If no solution is found, the UI displays "IRR: no solution" rather than a misleading number.

---

## D-009 · Revenue per Day: Tier 2 Warning Anchored to TEU Class

**Decision:** A Tier 2 warning (W-004) fires when `|entered revenue per day − anchor| > $5,000` for the vessel's TEU class. TEU is rounded to the nearest 1,000 before anchor lookup. Exactly $5,000 from the anchor does **not** warn. A separate rule (W-002) warns when effective daily revenue after off-hire is below OpEx per day.
**Reason:** The ±$5k threshold is grounded in the sample data provided (7,000 TEU → ~$40k/day; 8,000 TEU → ~$45k/day; 10,000 TEU → ~$50k/day; 12,000 TEU → ~$54k/day). A global threshold would be meaningless across vessel sizes.
**Trade-offs:** Anchors are seeded in `business_rules.py` and should be replaced with market data as the fleet grows. Thresholds live in `ValidationThresholds` (`schema.py`) so they can be refined without structural changes.

---

## D-010 · Scenario Design: Linked Inflation + Discount Rate Bundles

**Decision:** Best/Base/Worst scenarios are pre-defined bundles that pair an inflation rate and a discount rate together. Users can override individual values within a bundle (editable scenario table on the investment view), but defaults keep the pair economically consistent.
**Reason:** Inflation and discount rate are linked via the Fisher equation — nominal discount rates contain inflation expectations. Mixing best-case inflation (1%) with worst-case discount rate (12%) describes no real economic environment and would produce misleading results. Linked bundles prevent this by default.
**Default bundles:**

| Scenario | Inflation | Discount Rate |
|---|---|---|
| Best | 1% | 8% |
| Base | 3% | 10% |
| Worst | 5% | 12% |

The 2% spread (discount rate minus inflation) represents the real required return, held constant across scenarios. Base case matches the Excel reference inputs exactly.
**Trade-offs:** A user who genuinely wants to test inflation and discount rate independently can still do so by overriding values within a bundle. The tool warns (`scenario_bundles.py`) but does not block inconsistent pairs.

---

## D-011 · Validation Rules: Incremental Registry Pattern

**Decision:** Structural rules live in `STRUCTURAL_RULES`; business rules in `BUSINESS_RULES` — each entry is a typed object with id, message/check. Adding a rule means appending one list item.
**Reason:** Rules were discovered and refined while working through the sample data. The registry pattern keeps the validation engine stable while the rule set grows.
**Trade-offs:** TEU benchmark anchors and ±10% purchase-price tolerance remain calibration stubs until real fleet or market data supersedes them.

---

## D-012 · Dash Layout: Three Views

**Decision:** The app has three views accessible via tabs.
- **Investment summary:** Input panel, NPV/IRR/breakeven/payback cards, editable Best/Base/Worst scenario table, sensitivity chart (IRR vs. revenue per day).
- **Calculation detail:** Year-by-year cash flow table. Scenario selector (Best / Base / Worst / **Inputs** for the form's own rates); schedules from `decision_insights/scenario_schedules.py`.
- **Compare vessels:** Load up to 20 saved valuations; compare headline metrics and one cashflow line item on a shared chart.

**Reason:** Investment summary targets decision-makers; calculation detail targets analysts auditing the model; compare supports fleet-level judgment across saved runs. Per-year schedules for alternate scenarios are computed in a dedicated module (same rate overrides as `scenario_returns`) so summaries and detail stay aligned.

---

## D-013 · Database Migrations: Alembic

**Decision:** Use Alembic for database schema migrations, paired with SQLAlchemy ORM.
**Reason:** Alembic is the native migration tool for SQLAlchemy and follows the same workflow as Django migrations (autogenerate from model changes, versioned scripts, `upgrade head`). Django itself is not included — it would add the entire Django framework as a dependency for a single feature, conflicting with the Dash architecture.
**Trade-offs:** Alembic requires initial setup (env.py, alembic.ini). This is a one-time cost and the workflow is familiar to anyone who has used Django migrations.

---

## D-014 · Purchase Price Validation: PP÷TEU Ratio ±10%

**Decision:** The Tier 2 purchase-price check (W-003) compares **purchase price ÷ TEU** (not raw purchase price) against a benchmark ratio for the vessel's **exact** TEU size. A value outside ±10% of that benchmark triggers a warning. Benchmarks merge (1) medians from the **saved fleet** when at least two other vessels share the same exact TEU, with (2) case-study defaults from `data/case_study_pp_teu_benchmarks.json` when the database has no peer median.
**Reason:** PP÷TEU normalises price across capacity within a class. Median is robust to outliers in small samples — a single bad row like Vessel #8's $9M entry would distort a mean-based threshold. Exact-TEU keys avoid rounding unlike vessels into the same bucket incorrectly.
**Trade-offs:** Other rows in the **same upload file are not** used as PP÷TEU peers during Pass 2 (see D-015) — only saved fleet + case-study seeds — so one corrupt spreadsheet row cannot shift warnings for valid rows. The ±10% tolerance is configurable via `ValidationThresholds.price_tolerance`.

---

## D-015 · File Upload Validation: Two-Pass Strategy

**Decision:** File uploads run validation in two sequential passes. **Pass 1:** Tier 1 structural checks per row — rows with hard errors are flagged and excluded from coercion. **Pass 2:** Tier 2 business rules on each coerced row, using saved-fleet PP÷TEU peers (leave-one-out at the same exact TEU) when available, otherwise case-study defaults — **not** medians computed from other rows in the same upload.
**Reason:** Prevents a corrupt row (e.g. Vessel #8) from contaminating peer statistics used to validate valid rows. Pass 1 exclusion is the correct isolation mechanism.
**Trade-offs:** `ParseResult.batch_pp_teu_factor_benchmarks` aggregates upload-row medians for diagnostics and tests but is not applied during Pass 2 validation. Rows with Tier 1 errors must be fixed in the source file and re-uploaded.

---

## D-016 · Extra Vessel Metadata: Stored, Not Computed

**Decision:** Fields present in the sample data that do not feed the DCF model (`engine_type`, `co2_carbon_factor`) are stored as optional metadata in `vessel_inputs` and displayed as read-only information in the UI. They are not used in any calculation. `lw_tonnage` is required and stored; residual value is a required input — `SCRAP_RATE_PER_TONNE` in `schema.py` documents the case-study scrap convention but is not applied when residual is omitted because residual is always required after Tier 1.
**Reason:** Discarding metadata from an upstream source is an anti-pattern — it cannot be recovered later. Storing it costs nothing and enables future enrichment (e.g. ESG scoring, emissions reporting).

---

## D-017 · TEU Size: Required Input Field

**Decision:** TEU size is a required field in both the manual entry form and file uploads.
**Reason:** TEU size drives Tier 2 purchase-price and revenue benchmarks (D-014, D-009). TEU is also the primary vessel classification dimension in container shipping.

---

## D-018 · Configuration: .env File via python-dotenv

**Decision:** All environment-specific configuration (`DATABASE_URL`, app port, debug flag) is loaded from a `.env` file via `python-dotenv` in `config.py`. The `.env` file is gitignored; a `.env.example` with placeholder values is committed. Feature modules read settings through `config` getters, not `os.environ` directly.
**Reason:** Standard practice for secrets management in Python applications. Allows Docker Compose, local dev, and CI to each supply their own values without code changes. Centralising URL defaults documents runtime (in-memory SQLite) vs migration (file SQLite) vs Postgres behaviour in one place.

---

## D-019 · Upload Warnings: Row Select → Form Edit

**Decision:** When a file upload row passes Tier 1 but fails a Tier 2 check, it appears in the upload summary table with amber status and messages. The user **selects** the row to load parsed values into the manual form, corrects fields there, and runs **Calculate** — the upload table itself is read-only (not inline-editable cells).
**Reason:** Keeps correction in the same validated form path as manual entry without re-uploading the whole file for one borderline value. Re-validation uses the same fleet-peer and case-study benchmark rules as the initial parse (D-015).
**Trade-offs:** Tier 1 errors still require fixing the source spreadsheet and re-uploading.

---

## D-020 · TEU Benchmark Table: Self-Improving Gold Layer

**Decision:** `vessel_benchmarks` stores the **median purchase price** per TEU bucket (TEU rounded to nearest 1,000). Seeded on first migration from case-study sample medians; rebuilt when vessels are saved or deleted. `lookup_purchase_price_benchmark()` linearly interpolates between adjacent buckets when no exact bucket exists.
**Reason:** Hardcoded price tables go stale. A gold benchmark table supports fleet analytics and future features without re-ingesting bronze data.
**Note:** Tier 2 purchase-price **warnings** use PP÷TEU ratios (D-014), not this table. `vessel_benchmarks` is the purchase-price median store; PP÷TEU fleet medians come from `load_pp_teu_factor_benchmarks()`.

---

## D-021 · Sensitivity Analysis: User-Defined Range, $1,000 Steps

**Decision:** The sensitivity chart (IRR vs. revenue per day) uses a user-defined min and max revenue per day as the range, with $1,000 increment steps between them as required by the case study. There is no hardcoded global range.
**Reason:** A fixed range (e.g. ±$15k) is arbitrary. Different vessels have materially different charter rates (sample data spans $40k–$54k/day depending on TEU class). Letting the user define the range makes the tool useful across vessel types.
**Trade-offs:** Defaults (min = entered rate − $5,000, max = entered rate + $5,000) are pre-filled so the user gets a sensible chart immediately without manual adjustment.

---

## D-022 · Compare View: Up to 20 Saved Vessels

**Decision:** A third tab lets the user select 2–20 saved valuations and compare headline metrics plus one cashflow line item (e.g. free cashflow) on a single chart over aligned calendar years.
**Reason:** The product goal is executive comparison across vessels and assumptions, not a single invest/pass verdict. Reusing persisted gold schedules avoids recomputing every comparison from scratch in the UI.
**Trade-offs:** Selection is capped at 20 for chart readability; duplicate vessel input ids in one comparison are rejected.

---

## D-023 · Save to Database: Explicit Persist + Duplicate Guard

**Decision:** Upload parsing and **Calculate** do not write to the database. The user must click **Save to database** after a successful run. Save rejects duplicates: the same `vessel_name` (case-insensitive), `purchase_date`, and `teu_size` cannot be stored twice — the user must load the existing entry or change identity fields.
**Reason:** Separates exploratory calculation from fleet registry commits. Duplicate guard prevents accidental double-counting in fleet medians and compare lists.
**Trade-offs:** Batch upload does not persist all valid rows in one action (future production enhancement).
