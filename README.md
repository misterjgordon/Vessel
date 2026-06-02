# Vessel

DCF valuation for vessel.....

## Quick start

```bash
git clone git@github.com:misterjgordon/Vessel.git
cd Vessel
./install.sh
./run.sh
```

Open http://localhost:8050. Data is stored in **SQLite** (`vessel_valuation.db` in the project root). Code changes reload automatically. Stop the server with Ctrl+C.

`install.sh` installs [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed, syncs dependencies (Python 3.14 via the project pin), and runs database migrations. Run it again after pulling dependency changes.

Day-to-day after the first install:

```bash
./run.sh
```

Or with Make: `make dev` (install: `make install` or `make start` to install and run in one step).

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
- `tests/integration/` — mirrors `src/vessel_valuation/` (e.g. `db/test_repository.py`)
- `docs/writeup.md` — approach, insights, known gaps

## Using the app

1. Enter inputs or upload a file and select a **valid row**.
2. Click **Calculate valuation**, then **Save to database** (banner shows entry `#id`).
3. **Saved vessels** — pick any entry by `#id` to load or **Delete selected** (with confirmation).
4. **Compare vessels** — choose any two saved entries from the same database list.
