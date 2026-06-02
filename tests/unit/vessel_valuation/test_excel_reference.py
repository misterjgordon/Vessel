"""
Contract tests against the case study Excel reference model.
uv run --extra dev pytest tests/unit/vessel_valuation/test_excel_reference.py -v
"""

import pytest

from vessel_valuation.excel_reference import load_sample_vessels
from vessel_valuation.excel_reference import read_basic_inputs
from vessel_valuation.excel_reference import read_basic_outputs


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
