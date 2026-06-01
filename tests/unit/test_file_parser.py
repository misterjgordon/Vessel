# Run: uv run --extra dev pytest tests/unit/test_file_parser.py -v
"""File parser tests — header validation, two-pass validation, sample workbook."""

import io
import json
from pathlib import Path

import pandas as pd

from vessel_valuation.excel_reference import load_sample_vessels
from vessel_valuation.file_parser import (
    REQUIRED_COLUMNS,
    parse_dataframe,
    parse_upload,
)
from vessel_valuation.schema import VesselInputs
from vessel_valuation.validation import validate

_VALID_ROW: dict[str, object] = {
    'vessel_name': 'Test Vessel',
    'purchase_price': 100_000_000,
    'vessel_life': 25,
    'residual_value': 5_000_000,
    'lw_tonnage': 12_500,
    'revenue_per_day': 50_000,
    'offhire_rate': 0.02,
    'opex_per_day': 10_000,
    'drydock_capex': 5_000_000,
    'drydock_frequency': 5,
    'upgrades_capex': 500_000,
    'inflation_rate': 0.03,
    'discount_rate': 0.10,
    'days_of_year': 365,
    'teu_size': 10_000,
    'purchase_date': '2025-12-31',
    'engine_type': None,
    'co2_carbon_factor': None,
}


def _df(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    return pd.DataFrame(rows).to_csv(index=False).encode()


def _xlsx_bytes(rows: list[dict[str, object]]) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    return buf.getvalue()


def test_required_columns_match_vessel_inputs_fields() -> None:
    """REQUIRED_COLUMNS matches every VesselInputs field name."""
    import dataclasses

    from vessel_valuation.schema import VesselInputs

    all_fields = frozenset(f.name for f in dataclasses.fields(VesselInputs))
    assert REQUIRED_COLUMNS == all_fields


def test_required_headers_accepted() -> None:
    """VesselInputs snake_case column names are accepted without header errors."""
    result = parse_dataframe(_df([_VALID_ROW]))
    assert result.ok
    assert result.header_errors == []


def test_case_study_display_headers_are_mapped() -> None:
    """Case-study Sample Data column labels map to VesselInputs and parse successfully."""
    display_row = {
        'Input Field': 'Test Vessel',
        'TEU Size': 10_000,
        'LWT': 12_500,
        'Vessel Purchase Date': '2025-12-31',
        'Vessel Purchase Price': 100_000_000,
        'Vessel Expect Life': 25,
        'Vessel Residual Value': 5_000_000,
        'Revenue per Day': 50_000,
        'Days of a Year': 365,
        'Offhire Rate %': 0.02,
        'Operating Expense (OpEx) per Day': 10_000,
        'Drydock CapEx Cost': 5_000_000,
        'Drydock Frequency': 5,
        'Upgrades CapEx Cost': 500_000,
        'Inflation Rate Assumption': 0.03,
        'Discount Rate Assumption': 0.10,
        'Engine': None,
        'CO2 Carbon Factor': None,
    }
    result = parse_dataframe(_df([display_row]))
    assert result.ok, result.header_errors
    assert result.rows[0].ok
    assert result.rows[0].inputs is not None
    assert result.rows[0].inputs.vessel_name == 'Test Vessel'


def test_missing_display_header_maps_to_missing_field_error() -> None:
    """A missing case-study label reports the underlying VesselInputs field name."""
    display_row = {
        'Input Field': 'Test Vessel',
        'TEU Size': 10_000,
    }
    result = parse_dataframe(_df([display_row]))
    assert not result.ok
    assert any('purchase_price' in err for err in result.header_errors)


def test_row_raw_dict_uses_vessel_inputs_keys_only() -> None:
    """Parsed row payloads contain only VesselInputs keys, not extra upload columns."""
    row = dict(_VALID_ROW)
    row['extra_column'] = 'ignored'
    result = parse_dataframe(_df([row]))
    assert result.ok
    raw_keys = frozenset(result.rows[0].raw.keys())
    assert raw_keys == REQUIRED_COLUMNS


def test_missing_required_column_returns_header_error() -> None:
    """A missing required column blocks all row parsing and reports the missing name."""
    incomplete = {k: v for k, v in _VALID_ROW.items() if k != 'purchase_price'}
    result = parse_dataframe(_df([incomplete]))
    assert not result.ok
    assert any('purchase_price' in e for e in result.header_errors)
    assert result.rows == []


def test_multiple_missing_columns_all_reported() -> None:
    """Every missing required column is reported, not just the first."""
    drop = {'purchase_price', 'vessel_life', 'lw_tonnage'}
    incomplete = {k: v for k, v in _VALID_ROW.items() if k not in drop}
    result = parse_dataframe(_df([incomplete]))
    assert len(result.header_errors) == 3


def test_extra_columns_are_ignored() -> None:
    """Columns beyond the required set are silently ignored and do not affect parsing."""
    row = dict(_VALID_ROW)
    row['totally_unknown_field'] = 'ignored'
    result = parse_dataframe(_df([row]))
    assert result.ok


# ---------------------------------------------------------------------------
# Pass 1 — Tier 1 per-row validation
# ---------------------------------------------------------------------------


def test_valid_row_produces_no_errors() -> None:
    """A fully valid row passes Tier 1 and yields a populated VesselInputs."""
    result = parse_dataframe(_df([_VALID_ROW]))
    assert result.rows[0].ok
    assert result.rows[0].inputs is not None


def test_sentinel_in_numeric_field_produces_tier1_error() -> None:
    """An Excel sentinel string in a numeric field fails Tier 1 and blocks coercion."""
    row = dict(_VALID_ROW)
    row['purchase_price'] = '#VALUE!'
    result = parse_dataframe(_df([row]))
    assert not result.rows[0].ok
    assert result.rows[0].inputs is None


def test_nan_in_required_field_produces_tier1_error() -> None:
    """NaN in a required numeric field fails Tier 1."""
    row = dict(_VALID_ROW)
    row['lw_tonnage'] = float('nan')
    result = parse_dataframe(_df([row]))
    assert not result.rows[0].ok


def test_zero_purchase_price_produces_tier1_error() -> None:
    """Zero purchase price fails Tier 1 validation."""
    row = dict(_VALID_ROW)
    row['purchase_price'] = 0
    result = parse_dataframe(_df([row]))
    assert not result.rows[0].ok


def test_blank_rows_are_skipped() -> None:
    """Wholly empty rows are not counted as vessels in the parse result."""
    blank_row: dict[str, object] = {field: '' for field in REQUIRED_COLUMNS}
    result = parse_dataframe(_df([_VALID_ROW, blank_row, _VALID_ROW]))
    assert len(result.rows) == 2
    assert result.rows[0].row_number == 2
    assert result.rows[1].row_number == 4


def test_parse_result_exposes_batch_pp_teu_factor_benchmarks() -> None:
    """batch_pp_teu_factor_benchmarks on ParseResult matches valid upload rows."""
    from vessel_valuation.validation import median_pp_teu_factor

    rows = [dict(_VALID_ROW), dict(_VALID_ROW)]
    rows[1]['vessel_name'] = 'Second'
    result = parse_dataframe(_df(rows))
    assert result.batch_pp_teu_factor_benchmarks == median_pp_teu_factor(result.valid_inputs)


def test_row_numbers_match_spreadsheet_rows() -> None:
    """Row numbers are 1-based spreadsheet line numbers (row 1 = header)."""
    rows = [dict(_VALID_ROW), dict(_VALID_ROW)]
    rows[1]['vessel_name'] = 'Second Vessel'
    result = parse_dataframe(_df(rows))
    assert result.rows[0].row_number == 2
    assert result.rows[1].row_number == 3


def test_mixed_valid_and_invalid_rows() -> None:
    """Valid and invalid rows are processed independently; error count reflects only failed rows."""
    bad_row = dict(_VALID_ROW)
    bad_row['purchase_price'] = '#VALUE!'
    result = parse_dataframe(_df([_VALID_ROW, bad_row]))
    assert result.rows[0].ok
    assert not result.rows[1].ok
    assert result.error_count == 1


# ---------------------------------------------------------------------------
# Pass 2 — Tier 2 business rule warnings
# ---------------------------------------------------------------------------


def test_clean_row_has_no_warnings() -> None:
    """A benchmark-consistent row produces no Tier 2 warnings."""
    result = parse_dataframe(_df([_VALID_ROW]))
    assert result.rows[0].warnings == []


def test_residual_exceeding_purchase_price_triggers_warning() -> None:
    """Residual value above purchase price triggers a Tier 2 warning without blocking compute."""
    row = dict(_VALID_ROW)
    row['residual_value'] = 200_000_000
    result = parse_dataframe(_df([row]))
    assert result.rows[0].ok
    assert result.rows[0].has_warnings


def test_tier1_error_row_has_no_tier2_warnings() -> None:
    """Tier 2 checks are skipped entirely for rows that fail Tier 1."""
    row = dict(_VALID_ROW)
    row['purchase_price'] = 'n/a'
    result = parse_dataframe(_df([row]))
    assert not result.rows[0].ok
    assert result.rows[0].warnings == []


def test_upload_pp_teu_uses_case_study_when_no_db_peers() -> None:
    """Without DB peers, upload rows are checked against case-study PP÷TEU medians, not batch mates.

    Two 10,000 TEU vessels at $100M match the case-study median (10,000×).
    A third at $9M in the same file still warns against case study, not an in-batch median.
    """
    normal_row = dict(_VALID_ROW)

    cheap_row = dict(_VALID_ROW)
    cheap_row['vessel_name'] = 'Cheap Vessel'
    cheap_row['purchase_price'] = 9_000_000  # far below $100M batch median

    result = parse_dataframe(_df([normal_row, normal_row, cheap_row]))
    # The cheap vessel should have a price warning
    cheap = result.rows[2]
    assert cheap.ok  # Tier 1 passes
    assert cheap.has_warnings
    assert any('purchase-price÷teu ratio' in w.lower() for w in cheap.warnings)


def test_batch_price_check_uses_exact_teu_not_rounded_bucket() -> None:
    """7,500 TEU peers must not shift the benchmark for an 8,000 TEU vessel (D-014)."""
    row_7500_low = dict(_VALID_ROW)
    row_7500_low['teu_size'] = 7_500
    row_7500_low['purchase_price'] = 50_000_000
    row_7500_low['vessel_name'] = 'Seven Five Low'

    row_7500_high = dict(_VALID_ROW)
    row_7500_high['teu_size'] = 7_500
    row_7500_high['purchase_price'] = 60_000_000
    row_7500_high['vessel_name'] = 'Seven Five High'
    row_7500_high['purchase_date'] = '2026-02-01'

    row_8000_a = dict(_VALID_ROW)
    row_8000_a['teu_size'] = 8_000
    row_8000_a['purchase_price'] = 90_000_000
    row_8000_a['vessel_name'] = 'Eight A'

    row_8000_b = dict(_VALID_ROW)
    row_8000_b['teu_size'] = 8_000
    row_8000_b['purchase_price'] = 90_000_000
    row_8000_b['vessel_name'] = 'Eight B'
    row_8000_b['purchase_date'] = '2026-03-01'

    result = parse_dataframe(_df([row_7500_low, row_7500_high, row_8000_a, row_8000_b]))
    for row in result.rows:
        if row.inputs and row.inputs.teu_size == 8_000:
            assert not any('Purchase-price÷TEU ratio' in w for w in row.warnings)


def test_upload_row_warns_when_pp_teu_factor_differs_from_saved_fleet() -> None:
    """A new upload row is checked against saved 8,000 TEU fleet PP/TEU factors, not batch-only."""
    fleet_inputs: list[VesselInputs] = []
    for idx, price in enumerate((9_000_000.0, 90_000_000.0, 90_000_000.0)):
        row = dict(_VALID_ROW)
        row['teu_size'] = 8_000
        row['purchase_price'] = price
        row['vessel_name'] = f'Fleet Peer {idx}'
        row['purchase_date'] = f'2026-0{idx + 1}-01'
        inputs = validate(row).inputs
        assert inputs is not None
        fleet_inputs.append(inputs)

    new_row = dict(_VALID_ROW)
    new_row['teu_size'] = 8_000
    new_row['purchase_price'] = 55_000_000.0
    new_row['vessel_name'] = 'test vessel #12'
    new_row['purchase_date'] = '2026-03-31'

    result = parse_dataframe(_df([new_row]), fleet_peer_inputs=fleet_inputs)
    row = result.rows[0]
    assert row.errors == []
    assert any('Purchase-price÷TEU ratio' in w for w in row.warnings)
    assert any('6,875' in w for w in row.warnings)


def test_two_8000_teu_vessels_at_90m_match_case_study_without_db() -> None:
    """Two 8,000 TEU vessels at $90M match the case-study PP÷TEU benchmark when the DB is empty."""
    row_a = dict(_VALID_ROW)
    row_a['teu_size'] = 8_000
    row_a['purchase_price'] = 90_000_000.0
    row_a['vessel_name'] = 'Eight A'
    row_b = dict(_VALID_ROW)
    row_b['teu_size'] = 8_000
    row_b['purchase_price'] = 90_000_000.0
    row_b['vessel_name'] = 'Eight B'
    row_b['purchase_date'] = '2026-02-01'
    result = parse_dataframe(_df([row_a, row_b]))
    for row in result.rows:
        assert row.errors == []
        assert not any('Purchase-price÷TEU ratio' in w for w in row.warnings)


def test_mixed_8000_teu_upload_uses_case_study_not_batch_peers() -> None:
    """$9M and $90M rows in one upload are each judged against case study, not each other."""
    row_cheap = dict(_VALID_ROW)
    row_cheap['teu_size'] = 8_000
    row_cheap['purchase_price'] = 9_000_000.0
    row_cheap['vessel_name'] = 'Cheap Eight'

    row_high = dict(_VALID_ROW)
    row_high['teu_size'] = 8_000
    row_high['purchase_price'] = 90_000_000.0
    row_high['vessel_name'] = 'High Eight A'
    row_high_b = dict(_VALID_ROW)
    row_high_b['teu_size'] = 8_000
    row_high_b['purchase_price'] = 90_000_000.0
    row_high_b['vessel_name'] = 'High Eight B'
    row_high_b['purchase_date'] = '2026-02-01'

    result = parse_dataframe(_df([row_cheap, row_high, row_high_b]))
    by_name = {str(r.raw.get('vessel_name')): r for r in result.rows}
    assert any('Purchase-price÷TEU ratio' in w for w in by_name['Cheap Eight'].warnings)
    assert not any('Purchase-price÷TEU ratio' in w for w in by_name['High Eight A'].warnings)
    assert not any('Purchase-price÷TEU ratio' in w for w in by_name['High Eight B'].warnings)


# ---------------------------------------------------------------------------
# ParseResult convenience properties
# ---------------------------------------------------------------------------


def test_error_count_and_warning_count() -> None:
    """ParseResult error_count and warning_count reflect distinct row-level outcomes."""
    bad_row = dict(_VALID_ROW)
    bad_row['purchase_price'] = '#VALUE!'
    warn_row = dict(_VALID_ROW)
    warn_row['residual_value'] = 999_000_000
    warn_row['vessel_name'] = 'Warn Vessel'

    result = parse_dataframe(_df([_VALID_ROW, bad_row, warn_row]))
    assert result.error_count == 1
    assert result.warning_count == 1


def test_valid_inputs_returns_only_tier1_passing_rows() -> None:
    """valid_inputs excludes rows that failed Tier 1, regardless of warning state."""
    bad_row = dict(_VALID_ROW)
    bad_row['purchase_price'] = 'n/a'
    result = parse_dataframe(_df([_VALID_ROW, bad_row]))
    assert len(result.valid_inputs) == 1


# ---------------------------------------------------------------------------
# File format handling — CSV and XLSX bytes
# ---------------------------------------------------------------------------


def test_parse_upload_csv_bytes() -> None:
    """CSV bytes are parsed and validated through the full pipeline."""
    data = _csv_bytes([_VALID_ROW])
    result = parse_upload(data, 'vessels.csv')
    assert result.ok
    assert len(result.rows) == 1
    assert result.rows[0].ok


def test_parse_upload_xlsx_bytes() -> None:
    """XLSX bytes are parsed and validated through the full pipeline."""
    data = _xlsx_bytes([_VALID_ROW])
    result = parse_upload(data, 'vessels.xlsx')
    assert result.ok
    assert len(result.rows) == 1
    assert result.rows[0].ok


def test_parse_upload_path(tmp_path: Path) -> None:
    """A Path to a CSV file is accepted in addition to raw bytes."""
    csv_file = tmp_path / 'vessels.csv'
    pd.DataFrame([_VALID_ROW]).to_csv(csv_file, index=False)
    result = parse_upload(csv_file, csv_file.name)
    assert result.ok
    assert result.rows[0].ok


# ---------------------------------------------------------------------------
# Case-study sample data (integration with real workbook)
# ---------------------------------------------------------------------------


def test_parse_upload_case_study_workbook(case_study_xlsx: Path) -> None:
    """Full case-study xlsx upload maps Sample Data headers without pre-processing."""
    result = parse_upload(case_study_xlsx, case_study_xlsx.name)
    assert result.ok, result.header_errors
    assert len(result.rows) == 11
    assert result.error_count == 1


def test_upload_store_payload_is_json_serializable(case_study_xlsx: Path) -> None:
    """Parsed row raw dicts are JSON-safe for Dash dcc.Store (no pandas Timestamp)."""
    result = parse_upload(case_study_xlsx.read_bytes(), case_study_xlsx.name)
    store_payload = {
        'rows': [
            {
                'row_number': row.row_number,
                'raw': row.raw,
                'errors': row.errors,
                'warnings': row.warnings,
            }
            for row in result.rows
        ],
    }
    json.dumps(store_payload)
    assert isinstance(result.rows[0].raw['purchase_date'], str)


def test_sample_workbook_parses_nine_valid_vessels(case_study_xlsx: Path) -> None:
    """Case-study sample sheet parses 11 rows and flags exactly one Tier 1 error."""
    df = load_sample_vessels(case_study_xlsx)
    result = parse_dataframe(df, source_name='sample_data')
    assert result.ok, result.header_errors
    assert len(result.rows) == 11
    assert result.error_count == 1


def test_sample_workbook_vessel_8_has_tier1_error(case_study_xlsx: Path) -> None:
    """Sample Vessel #8 fails Tier 1 due to LWT sentinel '-' making lw_tonnage invalid."""
    df = load_sample_vessels(case_study_xlsx)
    result = parse_dataframe(df, source_name='sample_data')
    vessel_8 = result.rows[7]  # 0-based index 7 = 'Sample Vessle #8'
    assert not vessel_8.ok
    assert vessel_8.inputs is None
    assert vessel_8.errors


def test_sample_workbook_vessel_8_row_number(case_study_xlsx: Path) -> None:
    """Sample Vessel #8 reports its spreadsheet line number (header on row 1)."""
    df = load_sample_vessels(case_study_xlsx)
    result = parse_dataframe(df, source_name='sample_data')
    assert result.rows[7].row_number == 9


def test_sample_workbook_all_nine_valid_vessels_have_inputs(case_study_xlsx: Path) -> None:
    """All Tier-1-passing rows yield populated VesselInputs instances."""
    df = load_sample_vessels(case_study_xlsx)
    result = parse_dataframe(df, source_name='sample_data')
    valid = [r for r in result.rows if r.ok]
    assert len(valid) == 10
    assert all(r.inputs is not None for r in valid)
