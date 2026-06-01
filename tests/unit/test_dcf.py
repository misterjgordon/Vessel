"""DCF engine tests — verified against the case-study Excel workbook.

uv run --extra dev pytest tests/unit/test_dcf.py -v
"""

from datetime import date

import pytest

from vessel_valuation.dcf import compute_npv_irr
from vessel_valuation.excel_reference import read_basic_inputs
from vessel_valuation.schema import DcfResult, VesselInputs


def _vessel_inputs_from_basic_sheet(path) -> VesselInputs:
    """Build a VesselInputs from the basic sheet, filling non-DCF fields.

    The basic sheet does not supply vessel_name, teu_size, or lw_tonnage.
    These are required for the schema but do not affect DCF calculations,
    so representative values consistent with the sample data are used.
    lw_tonnage=12500 derives residual_value = 12500 * 400 = $5,000,000,
    matching the basic sheet's own residual value exactly.
    """
    raw = read_basic_inputs(path)
    purchase_dt = raw['Vessel Purchase Date']
    purchase_date = (
        purchase_dt.date() if hasattr(purchase_dt, 'date') else date(purchase_dt.year, 12, 31)
    )
    return VesselInputs(
        vessel_name='Base Case',
        purchase_price=float(raw['Vessel Purchase Price']),
        vessel_life=int(raw['Vessel Expect Life']),
        residual_value=float(raw['Vessel Residual Value']),
        lw_tonnage=12500.0,
        revenue_per_day=float(raw['Revenue per Day']),
        offhire_rate=float(raw['Offhire Rate %']),
        opex_per_day=float(raw['Operating Expense (OpEx) per Day']),
        drydock_capex=float(raw['Drydock CapEx Cost']),
        drydock_frequency=int(raw['Drydock Frequency']),
        upgrades_capex=float(raw['Upgrades CapEx Cost']),
        inflation_rate=float(raw['Inflation Rate Assumption']),
        discount_rate=float(raw['Discount Rate Assumption']),
        days_of_year=int(raw['Days of a Year']),
        teu_size=10000,
        purchase_date=purchase_date,
    )


def test_compute_npv_irr_returns_dcf_result(case_study_xlsx) -> None:
    """compute_npv_irr returns a DcfResult without decision-insight fields."""
    inputs = _vessel_inputs_from_basic_sheet(case_study_xlsx)
    result = compute_npv_irr(inputs)
    assert isinstance(result, DcfResult)


def test_compute_npv_irr_matches_basic_sheet(case_study_xlsx) -> None:
    """Engine NPV and IRR match the case-study basic sheet golden values."""
    inputs = _vessel_inputs_from_basic_sheet(case_study_xlsx)
    result = compute_npv_irr(inputs)

    assert result.npv == pytest.approx(4_143_625.443279, rel=1e-4)
    assert result.irr == pytest.approx(0.105855, rel=1e-4)


def test_schedule_has_correct_length(case_study_xlsx) -> None:
    """Cashflow schedule spans year 0 plus one row per operating year."""
    inputs = _vessel_inputs_from_basic_sheet(case_study_xlsx)
    result = compute_npv_irr(inputs)

    assert len(result.schedule) == 26


def test_schedule_year_zero_is_purchase_outflow(case_study_xlsx) -> None:
    """Year 0 records the purchase outflow with no operating revenue."""
    inputs = _vessel_inputs_from_basic_sheet(case_study_xlsx)
    result = compute_npv_irr(inputs)

    year_zero = result.schedule[0]
    assert year_zero.year == 0
    assert year_zero.net_cashflow == pytest.approx(-100_000_000)
    assert year_zero.revenue == 0.0
    assert year_zero.period_end == date(2025, 12, 31)


def test_schedule_year_one_cashflow(case_study_xlsx) -> None:
    """Year 1 revenue, opex, upgrades, and free cashflow match the workbook."""
    inputs = _vessel_inputs_from_basic_sheet(case_study_xlsx)
    result = compute_npv_irr(inputs)

    year_one = result.schedule[1]
    assert year_one.revenue == pytest.approx(17_885_000)
    assert year_one.opex == pytest.approx(3_759_500)
    assert year_one.drydock_capex == 0.0
    assert year_one.upgrades_capex == pytest.approx(515_000)
    assert year_one.free_cashflow == pytest.approx(13_610_500)


def test_drydock_occurs_at_frequency_multiples_only(case_study_xlsx) -> None:
    """Drydock CapEx appears only in years that are multiples of the frequency."""
    inputs = _vessel_inputs_from_basic_sheet(case_study_xlsx)
    result = compute_npv_irr(inputs)

    drydock_years = [row.year for row in result.schedule if row.drydock_capex > 0]
    assert drydock_years == [5, 10, 15, 20]


def test_residual_value_in_final_year_only(case_study_xlsx) -> None:
    """Residual proceeds appear in the final year; other years net equals free cashflow."""
    inputs = _vessel_inputs_from_basic_sheet(case_study_xlsx)
    result = compute_npv_irr(inputs)

    final = result.schedule[-1]
    assert final.year == 25
    assert final.net_cashflow == pytest.approx(final.free_cashflow + 5_000_000)

    for row in result.schedule[1:-1]:
        assert row.net_cashflow == pytest.approx(row.free_cashflow)


def test_investment_signal_is_marginal_for_base_case(case_study_xlsx) -> None:
    """Base-case IRR near the discount rate yields a MARGINAL investment signal."""
    inputs = _vessel_inputs_from_basic_sheet(case_study_xlsx)
    result = compute_npv_irr(inputs)

    assert result.investment_signal == 'MARGINAL'


def test_payback_year_is_within_vessel_life(case_study_xlsx) -> None:
    """Payback year is defined and falls within the vessel operating life."""
    inputs = _vessel_inputs_from_basic_sheet(case_study_xlsx)
    result = compute_npv_irr(inputs)

    assert result.payback_year is not None
    assert 1 <= result.payback_year <= inputs.vessel_life
