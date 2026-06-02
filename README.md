# Vessel

Welles-style single-vessel DCF valuation for the Finance Solution Developer case study.

## Setup

```bash
cd /Users/joel/Github/Vessel
make sync
make dev
```

Open http://localhost:8050. The app uses **file-backed SQLite** (`vessel_valuation.db` in the project root). Code changes reload automatically (`DASH_DEBUG=1`). No Docker required for day-to-day work.

To stop: Ctrl+C in the terminal running `make dev`.

### Optional — Docker (Postgres + containerized app)

Only if you want to exercise Postgres locally. Requires Docker Desktop. **Rebuild the image after every code change** (`make docker-up`).

```bash
make docker-up    # http://localhost:8050, Postgres on localhost:5432
make docker-down  # stop containers
```

## Case study assets

- `docs/case_study/` — instructions (PDF) and reference model (xlsx)
- `data/source/` — copy of the model workbook for scripts/tests

## Tests

```bash
make test
make test-integration
```

Workbook contract tests read golden NPV/IRR from the Excel **Input & Output (Basic)** sheet.

## Layout

- `src/vessel_valuation/` — DCF engine, validation, file parser, decision insights, database repository
- `app/` — Dash UI (investment summary, calculation detail, compare vessels)
- `tests/unit/` — pytest mirroring `src/vessel_valuation/` and `app/` layout
- `tests/integration/` — repository round-trips (SQLite in-memory)
- `docs/writeup.md` — approach, insights, known gaps

## Using the app

1. Enter inputs or upload a file and select a **valid row**.
2. Click **Calculate valuation**, then **Save to database** (banner shows entry `#id`).
3. **Saved vessels** — pick any entry by `#id` to load or **Delete selected** (with confirmation).
4. **Compare vessels** — choose any two saved entries from the same database list.
