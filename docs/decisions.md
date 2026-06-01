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
**Trade-offs:** Adds upload parsing complexity. Mitigated by requiring headers to exactly match the defined `VesselInputs` data class fields. Invalid files are rejected early with a clear error message.

---

## D-003 · Data Model: Typed Dataclass for Vessel Inputs

**Decision:** All vessel inputs are represented by a single Python `dataclass` (`VesselInputs`). Field names are shared by the UI form and file upload header row.
**Reason:** A single source of truth for field names prevents drift between the form, the file parser, the validation layer, and the calculation engine. Downstream code only ever receives a validated `VesselInputs` instance.
**Trade-offs:** Adds a mapping step from raw Excel/CSV column names to dataclass fields. Acceptable given the small fixed field count.

---

## D-004 · Validation: Two-Tier Warning/Error System

**Decision:** Validation runs in two tiers. Tier 1 (errors): type or structural problems that prevent calculation — e.g. non-numeric purchase price, missing required field, `#VALUE!` literal. Tier 2 (warnings): values are valid types but fail a business-rule check — e.g. purchase price implausible for TEU size, residual value exceeds purchase price. The UI blocks calculation on Tier 1 errors; it shows warnings for Tier 2 but allows the user to proceed.
**Reason:** Directly motivated by the dirty data in Sample Vessel #8 (purchase price $9M vs. ~$90M pattern, `#VALUE!` residual). Separating hard errors from soft warnings gives the user actionable feedback without being unnecessarily blocking.
**Trade-offs:** Business rules (Tier 2) are placeholder stubs initially — they are architecture-ready but the specific thresholds will be refined. Rules are registered in a single `validation.py` module so they can be extended without touching UI or engine code.

---

## D-005 · Persistence: PostgreSQL with Medallion Layer Schemas

**Decision:** Use PostgreSQL as the persistence layer. The database is organised into three schemas that mirror the medallion architecture pattern — `raw`, `vessel`, and a results area — but all Python functions use business-domain names, not medallion terminology.
**Reason:** The 10-vessel sample set is seed data for a fleet registry, not a throwaway test fixture. The tool is explicitly meant to scale. Shipping without a real persistence story misrepresents the production intent. PostgreSQL is the industry-standard choice for structured financial data.
**Trade-offs:** Adds a dependency (Postgres running locally via Docker for dev). For the prototype the connection string is an environment variable so it degrades gracefully to a JSON fallback if no DB is available. Production deployment would add connection pooling, migrations (Alembic), and row-level auth.

## D-006 · Database Schema Design: Medallion Layers (Business-Named)

**Decision:** Three database schemas map to the three medallion layers, but all code (functions, classes, columns) uses business vocabulary — not bronze/silver/gold.

| Layer concept | Schema | What it holds |
|---|---|---|
| Bronze | `raw` | Every submission exactly as received — no transforms, nothing discarded |
| Silver | `vessel` | Validated, normalised vessel inputs (one clean record per vessel) |
| Gold | `vessel` | Computed results: NPV, IRR, cashflows, sensitivity runs, scenario outputs |

**Reason:** The medallion pattern ensures no raw data is ever lost (always recoverable), provides a clean audit trail from submission → validation → computation, and gives a natural upgrade path (re-run silver→gold computations without re-ingesting). Keeping names business-domain means the code is readable to finance stakeholders, not just engineers.

## D-008 · IRR Solver: scipy.optimize.brentq

**Decision:** Use `scipy.optimize.brentq` for the IRR calculation.
**Reason:** `numpy-financial`'s `npf.irr()` returns `NaN` silently when cash flows produce multiple sign changes or no real solution — the caller receives a meaningless number with no indication of failure. A parameter change (e.g. large inflation-adjusted drydock CapEx overwhelming revenue in a given year) could produce mid-life negative cash flows depending on user assumptions. `scipy.optimize.brentq` defines an explicit search bracket, raises a clear exception if no solution exists, and is fully controllable. Failures surface as errors in the UI rather than silent wrong answers.
**Trade-offs:** Requires choosing a bracket (e.g. −99% to +999%). The bracket is wide enough to cover all realistic vessel IRRs. If no solution is found, the UI displays "IRR: no solution" rather than a misleading number.

---

## D-013 · Database Migrations: Alembic

**Decision:** Use Alembic for database schema migrations, paired with SQLAlchemy ORM.
**Reason:** Alembic is the native migration tool for SQLAlchemy and follows the same workflow as Django migrations (autogenerate from model changes, versioned scripts, `upgrade head`). Django itself is not included — it would add the entire Django framework as a dependency for a single feature, conflicting with the Dash architecture.
**Trade-offs:** Alembic requires initial setup (env.py, alembic.ini). This is a one-time cost and the workflow is familiar to anyone who has used Django migrations.

---

## D-020 · TEU Benchmark Table: Self-Improving Gold Layer

**Decision:** A `vessel.benchmarks` gold table stores the median purchase price per TEU bucket (TEU rounded to nearest 1,000). It is seeded from the 9 valid sample vessels on first migration and rebuilt automatically every time a vessel is saved to `vessel.inputs`. For TEU sizes with no exact bucket entry, the validation layer linearly interpolates between the two nearest adjacent buckets. If no interpolation is possible (fewer than two neighbours), the Tier 2 purchase price check is skipped with an info notice.
**Reason:** Hardcoded benchmark tables go stale. Making the DB the source of truth for benchmarks means accuracy improves naturally as the fleet registry grows. Linear interpolation gives reasonable coverage for intermediate TEU sizes without needing manual data entry.
**Trade-offs:** Interpolation assumes a roughly linear price-to-TEU relationship, which is a simplification. In production, a more sophisticated regression could be applied. For this prototype, linear interpolation between adjacent buckets is sufficient and explainable.

---

## D-014 · Purchase Price Validation: TEU-Class Median ±10%

**Decision:** The Tier 2 purchase price warning compares an entered vessel's purchase price against the **median** purchase price of all other vessels with the same TEU size in the database. A value outside ±10% of that median triggers a warning. TEU size is a required input field.
**Reason:** Without sufficient data volume for standard deviation-based outlier detection, TEU class is the best available proxy for expected vessel value. Median is used (not mean) because it is robust to outliers in small samples — a single bad data point like Vessel #8's $9M entry would distort a mean-based threshold but not a median. Container vessels of the same TEU class are comparable assets; price divergence within a TEU class is meaningful signal.
**Trade-offs:** On a first upload with no existing data, the median is computed from the valid rows within the same upload batch (see D-015). The ±10% threshold is a starting assumption to be calibrated against real fleet transaction data in production.

---

## D-015 · File Upload Validation: Two-Pass Strategy

**Decision:** File uploads run validation in two sequential passes. Pass 1 applies Tier 1 structural checks only — rows with hard errors are flagged and excluded. Pass 2 computes TEU-class statistics from the valid rows surviving Pass 1, then applies Tier 2 business-rule checks against those statistics. Rows excluded in Pass 1 are never included in TEU-class medians.
**Reason:** Prevents a circular dependency where a corrupt row (e.g. Vessel #8 with `#VALUE!` residual and implausible $9M purchase price) contaminates the statistics used to validate the valid rows. Pass 1 exclusion is the correct isolation mechanism — simpler and more reliable than in-memory deferred processing.
**Trade-offs:** A row excluded in Pass 1 cannot be auto-corrected; the user must fix and re-upload it. This is intentional — the tool does not guess at what the correct value should be for hard errors.

---

## D-019 · Tier 2 Warnings: Inline Correction in Batch Upload Table

**Decision:** When a file upload row passes Tier 1 but fails a Tier 2 business rule check, it is displayed in the batch results table with an amber warning. The flagged field is **editable inline** — the user clicks the cell, corrects the value, and re-validation runs immediately against the same batch statistics. The user must explicitly confirm the corrected value before the row proceeds to computation.
**Reason:** Forcing a full re-upload for a single correctable warning is poor UX, especially for a 10-vessel batch where one vessel has a borderline purchase price. Inline correction keeps the user in the same workflow without restarting. Re-validating against batch statistics (not a fresh re-upload) ensures consistency.
**Trade-offs:** Inline editing only applies to Tier 2 warnings. Tier 1 errors require a corrected file re-upload — the data is structurally broken and should be fixed at the source.

---

## D-016 · Extra Vessel Metadata: Stored, Not Computed

**Decision:** Fields present in the sample data that do not feed the DCF model (Engine Type, CO2 Carbon Factor, LWT) are stored as optional metadata in `vessel.inputs` and displayed as read-only information in the UI. They are not used in any calculation.
**Reason:** Discarding metadata from an upstream source is an anti-pattern — it cannot be recovered later. Storing it costs nothing and enables future enrichment (e.g. ESG scoring, emissions reporting).

---

## D-017 · TEU Size: Required Input Field

**Decision:** TEU size is a required field in both the manual entry form and file uploads.
**Reason:** TEU size drives the Tier 2 purchase price validation (D-014). Without it, the cross-asset comparison cannot run. TEU is also the primary vessel classification dimension in container shipping.

---

## D-018 · Configuration: .env File via python-dotenv

**Decision:** All environment-specific configuration (DATABASE_URL, app port, debug flag) is loaded from a `.env` file via `python-dotenv` in `config.py`. The `.env` file is gitignored; a `.env.example` with placeholder values is committed. Feature modules read settings through `config` getters, not `os.environ` directly.
**Reason:** Standard practice for secrets management in Python applications. Allows Docker Compose, local dev, and CI to each supply their own values without code changes. Centralising URL defaults documents runtime (in-memory SQLite) vs migration (file SQLite) vs Postgres behaviour in one place.

---

## D-008 · Sensitivity Analysis: User-Defined Range, $1,000 Steps

**Decision:** The sensitivity chart (IRR vs. Revenue per Day) uses a user-defined min and max revenue per day as the range, with $1,000 increment steps between them as required by the case study. There is no hardcoded global range.
**Reason:** A fixed range (e.g. ±$15k) is arbitrary. Different vessels have materially different charter rates (sample data spans $40k–$54k/day depending on TEU class). Letting the user define the range makes the tool useful across vessel types.
**Trade-offs:** Defaults (min = entered rate − $5,000, max = entered rate + $5,000) are pre-filled so the user gets a sensible chart immediately without manual adjustment.

## D-009 · Revenue per Day: Tier 2 Warning Anchored to TEU Class

**Decision:** A Tier 2 warning fires if the entered revenue per day is more than $5,000 outside the expected range for the vessel's TEU class, based on sample data benchmarks. If TEU size is not provided, no warning is raised.
**Reason:** The ±$5k threshold is grounded in the sample data provided (7,000 TEU → ~$40k/day; 8,000 TEU → ~$45k/day; 10,000 TEU → ~$50k/day; 12,000 TEU → ~$54k/day). A global threshold would be meaningless across vessel sizes.
**Trade-offs:** Benchmarks are derived from 10 sample vessels and are stubs — they will need updating as more data is available. Thresholds are defined in a single config in `validation.py` so they can be refined without structural changes.

## D-010 · Scenario Design: Linked Inflation + Discount Rate Bundles

**Decision:** Best/Base/Worst scenarios are pre-defined bundles that pair an inflation rate and a discount rate together. Users can override individual values within a bundle, but defaults keep the pair economically consistent.
**Reason:** Inflation and discount rate are linked via the Fisher equation — nominal discount rates contain inflation expectations. Mixing best-case inflation (1%) with worst-case discount rate (12%) describes no real economic environment and would produce misleading results. Linked bundles prevent this by default.
**Default bundles:**

| Scenario | Inflation | Discount Rate |
|---|---|---|
| Best | 1% | 8% |
| Base | 3% | 10% |
| Worst | 5% | 12% |

The 2% spread (discount rate minus inflation) represents the real required return, held constant across scenarios. Base case matches the Excel reference inputs exactly.
**Trade-offs:** A user who genuinely wants to test inflation and discount rate independently can still do so by overriding values within a bundle. The tool warns but does not block inconsistent pairs.

## D-011 · Validation Rules: Incremental Registry Pattern

**Decision:** All validation rules are registered as typed objects in a single list in `validation.py`. Adding a new rule means appending one item — no structural changes required.
**Reason:** Rules will be discovered and refined as we work through the sample data. The registry pattern means the validation engine is stable while the rule set grows. Each rule declares its tier (1 = error / 2 = warning), its user-facing message, and its check function independently.
**Trade-offs:** Rules are stubs initially. Tier 2 thresholds (e.g. TEU-class revenue benchmarks) are placeholders that will need calibration against real market data in production.

## D-012 · Dash Layout: Two Views

**Decision:** The app has two views accessible via a tab or nav bar.
- **View 1 — Investment Summary**: Input panel, NPV/IRR output cards, scenario analysis table (Best/Base/Worst), inflation scenario comparison. Headline metrics first; no year-by-year table here.
- **View 2 — Calculation Detail**: Year-by-year cash flow table replicating the Excel Calculation sheet. A scenario selector (Best / Base / Worst / **Inputs** for the form’s own rates) drives which schedule is shown; schedules come from `decision_insights/scenario_schedules.py`, not from ad hoc callback logic.
**Reason:** View 1 is for decision-makers who want a headline number. View 2 is for analysts who want to audit the model or trace a specific year. Separating them keeps View 1 uncluttered. Per-year schedules for alternate scenarios are computed in a dedicated module (same rate overrides as `scenario_returns`) so View 1 summaries and View 2 detail stay aligned.

## D-007 · UI/Engine Separation

**Decision:** Dash callback functions contain zero business logic. Every callback's job is exactly: collect inputs → call a function from `model.py`, `decision_insights/`, or `db/repository.py` → pass the result to a Dash component. No formulas, no data transforms, no SQL in callbacks.
**Reason:** Makes the entire engine independently testable without a running browser. The same `compute_npv_irr()` that the UI calls is what `make test` exercises. Swapping Dash for an API or notebook later requires no changes to any logic module.
