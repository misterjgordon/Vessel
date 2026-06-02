# Vessel Valuation Tool — Write-up

## Design approach

The tool mirrors the case-study Excel DCF: Year 0 purchase outflow, annual operating cash flows with inflation on costs only, drydock on a fixed frequency, and residual proceeds in the final year. The Python engine is pure functions in `src/vessel_valuation/` with no UI dependencies; golden NPV and IRR tests lock behaviour to the reference workbook.

Architecture follows three product pillars—input, calculate, and insights—mapped to three code layers. The Dash app in `app/` wires callbacks only. The logic layer validates inputs, runs the DCF engine, and builds decision analytics (breakeven charter rate, IRR sensitivity, macro scenarios). The data layer persists through a repository with SQLAlchemy and Alembic; ORM models never leak into callbacks.

A single `VesselInputs` dataclass is the field-name source of truth for the form, file upload headers, validation, and engine. Two-tier validation separates blocking structural errors (Tier 1) from advisory business rules (Tier 2). Valid submissions follow a bronze → silver → gold persist path: raw submission, normalised inputs, then valuation and base cashflow schedule. The UI calls validation, `enrich()`, and the repository—never formulas or SQL in the app layer.

Inputs arrive via manual form or CSV/Excel upload. Users calculate, optionally save to the database, reload prior entries, and compare up to 20 saved vessels on a single schedule line item. Scenario schedules for the calculation tab are recomputed on demand so storage stays bounded.

## Key assumptions made

The case study brief defines the DCF mechanics and timing; those are documented in [assumptions.md](assumptions.md). The items below are implementation choices, mostly inferred from the 8-vessel sample workbook rather than stated in the instructions.

The sample sheet serves as the initial reference fleet. It is not a machine-learned model, but it is the only real data available for calibrating data-quality rules. Purchase-price checks use the median price (or purchase-price÷TEU ratio) among peers with the same TEU size, with a ±10% band around that median. Median is preferred over mean so a single bad row—such as the vessel with a $9M price and `#VALUE!` residual—does not pull the threshold for everyone else. Revenue-per-day warnings use fixed charter-rate anchors per TEU bucket ($40k–$54k/day) taken from the same sample rows, with a ±$5,000 tolerance. Those numbers are committed as seeds and in a small JSON benchmark file until enough vessels are saved in the database to replace them.

TEU is rounded to the nearest 1,000 for grouping because the sample only spans a handful of sizes. When a TEU bucket has no saved median, validation falls back to the case-study seeds or linear interpolation between the nearest buckets; price is assumed to scale roughly linearly between 7k, 8k, 10k, and 12k TEU classes. File upload runs in two passes: structural errors are stripped first, then Tier 2 rules in `business_rules.py` run on the remaining rows so corrupt lines never enter the peer statistics.

Other implementation choices: golden NPV and IRR in `tests/unit/vessel_valuation/test_dcf.py` are taken from the Excel basic sheet, not re-derived from the PDF alone. Default scenario bundles pair inflation and discount so the nominal gap (discount minus inflation) is the same in Best, Base, and Worst (seven percentage points in the shipped defaults); the UI warns if edited bundles break that consistency. Optional metadata from the sample (engine type, CO2 factor) is stored but not used in cashflows; LWT is required and stored but the engine uses the entered residual value directly—a `$400`/light-tonne constant exists in `schema.py` for documentation and test fixtures but is not applied at runtime when residual is absent, because residual is a required field. Upload parses and validates all rows but does not persist them until the user runs calculate and clicks save.

## Scaling to production use

The prototype deliberately uses SQLite only—a single file database for local use, tests, and the Dash app—rather than running Postgres in development. The repository and Alembic migrations are written to stay portable, but production was not wired to a second engine for this deliverable. A practical production path would move the same schema to PostgreSQL for concurrent access and managed backups, add Django (or Django REST) for user accounts, permissions, and row-level access to saved valuations, and host the stack on a managed platform such as Render, with the existing valuation logic remaining a shared Python package behind the web tier.

Workbook-aligned pytest guards the engine, so new features can extend validation or insights modules without touching Dash layouts. Scenario and sensitivity logic live under `decision_insights/` so a batch job or API could call the same functions later.

Saving vessels refreshes TEU benchmarks from stored data, so accuracy improves as the fleet registry grows. Bronze retains every raw submission for audit and reprocessing if silver or gold rules change.

Beyond that database and hosting shift, likely next steps include replacing stub benchmarks with market or ERP feeds, batch persist and fleet ranking for multi-row uploads, and PDF or Excel export for board packs. Compute is stateless aside from persistence, so additional capacity is mostly more application workers against shared PostgreSQL; heavier analytics could move to background jobs or an API that still takes `VesselInputs` and calls `enrich()`.
