# Run: uv run --extra dev pytest tests/unit/test_case_study_workbook.py -v
"""Contract tests against the case study Excel reference model."""

import pytest

from vessel_valuation.case_study_benchmarks import load_case_study_pp_teu_benchmarks
from vessel_valuation.excel_reference import (
    build_pp_teu_benchmarks_from_workbook,
    load_sample_vessels,
    read_basic_inputs,
    read_basic_outputs,
)


def test_case_study_assets_exist(case_study_xlsx, case_study_pdf) -> None:
    """Bundled case-study workbook and PDF fixtures are present and non-empty."""
    assert case_study_xlsx.stat().st_size > 0
    assert case_study_pdf.stat().st_size > 0


def test_basic_sheet_golden_npv_irr(case_study_xlsx) -> None:
    """Excel reference reader returns the basic sheet NPV and IRR golden values."""
    outputs = read_basic_outputs(case_study_xlsx)
    assert outputs['npv'] == pytest.approx(4_143_625.443279, rel=1e-6)
    assert outputs['irr'] == pytest.approx(0.10585531076966781, rel=1e-9)


def test_basic_sheet_inputs_load(case_study_xlsx) -> None:
    """Basic sheet input cells load with expected purchase price, life, and discount rate."""
    inputs = read_basic_inputs(case_study_xlsx)
    assert inputs['Vessel Purchase Price'] == 100_000_000
    assert inputs['Vessel Expect Life'] == 25
    assert inputs['Discount Rate Assumption'] == 0.1


def test_sample_vessels_sheet_has_ten_rows(case_study_xlsx) -> None:
    """Sample vessels sheet loads ten rows with VesselInputs column names."""
    df = load_sample_vessels(case_study_xlsx)
    assert len(df) == 11
    assert 'purchase_price' in df.columns


def test_bundled_pp_teu_benchmarks_match_case_study_workbook(case_study_xlsx) -> None:
    """Bundled PP÷TEU JSON matches medians computed from the case-study sample sheet."""
    from_workbook = build_pp_teu_benchmarks_from_workbook(case_study_xlsx)
    bundled = load_case_study_pp_teu_benchmarks()
    assert bundled == from_workbook
