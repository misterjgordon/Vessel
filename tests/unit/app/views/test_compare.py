"""Unit tests for vessel cashflow comparison presentation.

uv run --extra dev pytest tests/unit/app/views/test_compare.py -v
"""

from datetime import date

from app.views.compare import CompareVessel
from app.views.compare import build_compare_schedule_rows
from app.views.compare import build_compare_summary_rows
from app.views.compare import parse_compare_vessel_selection
from app.views.compare import validate_compare_metric
from vessel_valuation.schema import CashflowYear
from vessel_valuation.schema import ValuationResult


def _cashflow_year(year: int, fcf: float, revenue: float = 0.0) -> CashflowYear:
    period_end = date(2025 + year, 12, 31)
    return CashflowYear(
        year=year,
        period_end=period_end,
        revenue=revenue,
        opex=0.0,
        drydock_capex=0.0,
        upgrades_capex=0.0,
        free_cashflow=fcf,
        net_cashflow=fcf,
        discounted_cashflow=0.0,
        cumulative_cashflow=0.0,
    )


def _valuation(schedule: list[CashflowYear], npv: float = 1.0) -> ValuationResult:
    return ValuationResult(
        npv=npv,
        irr=0.1,
        schedule=schedule,
        payback_year=5,
        investment_signal='FAVORABLE',
    )


def test_parse_compare_vessel_selection_rejects_too_few() -> None:
    """Fewer than two vessel ids returns an error message."""
    ids, message = parse_compare_vessel_selection([1])
    assert ids is None
    assert '2' in message


def test_parse_compare_vessel_selection_rejects_duplicates() -> None:
    """Duplicate ids in the selection are rejected."""
    ids, message = parse_compare_vessel_selection([1, 1])
    assert ids is None
    assert 'duplicates' in message.lower()


def test_build_compare_schedule_rows_aligns_mismatched_lives() -> None:
    """Rows cover the union of years; delta appears for exactly two vessels."""
    schedule_a = [_cashflow_year(0, -100.0), _cashflow_year(1, 10.0)]
    schedule_b = [_cashflow_year(0, -80.0), _cashflow_year(2, 5.0)]
    vessels = [
        CompareVessel(1, 'Alpha', _valuation(schedule_a)),
        CompareVessel(2, 'Beta', _valuation(schedule_b)),
    ]

    rows = build_compare_schedule_rows(vessels, 'free_cashflow')

    assert [row['year'] for row in rows] == [0, 1, 2]
    assert rows[1]['delta'] == '$10'
    assert rows[2]['vessel_1'] == '$0'


def test_build_compare_schedule_rows_uses_selected_metric() -> None:
    """Schedule table reads the chosen line item field, not always free cashflow."""
    schedule = [_cashflow_year(1, fcf=0.0, revenue=50_000.0)]
    vessels = [CompareVessel(3, 'Gamma', _valuation(schedule))]

    rows = build_compare_schedule_rows(vessels, 'revenue')

    assert rows[0]['vessel_3'] == '$50.0k'


def test_validate_compare_metric_falls_back_to_default() -> None:
    """Unknown metric values resolve to free cashflow."""
    assert validate_compare_metric('not_a_field') == 'free_cashflow'


def test_build_compare_summary_rows_formats_metrics() -> None:
    """Summary rows include vessel name and formatted NPV / IRR / signal."""
    vessels = [
        CompareVessel(1, 'Alpha', _valuation([_cashflow_year(0, 0.0)], npv=1_500_000.0)),
    ]

    rows = build_compare_summary_rows(vessels)

    assert rows[0]['vessel'] == 'Alpha'
    assert rows[0]['npv'] == '$1.50m'
    assert rows[0]['signal'].startswith('Favorable')
