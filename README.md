# Vessel

Welles-style single-vessel DCF valuation for the Finance Solution Developer case study.

## Setup

```bash
cd /Users/joel/Github/Vessel
make sync
```

## Case study assets

- `docs/case_study/` — instructions (PDF) and reference model (xlsx)
- `data/source/` — copy of the model workbook for scripts/tests

## Tests

```bash
make test
```

Workbook contract tests read golden NPV/IRR from the Excel **Input & Output (Basic)** sheet. Valuation logic tests are skipped until `vessel_valuation` implements the DCF engine.

## Layout

- `src/vessel_valuation/` — valuation engine (to implement)
- `tests/unit/` — pytest against Excel reference outputs
- `scripts/` — optional helpers
