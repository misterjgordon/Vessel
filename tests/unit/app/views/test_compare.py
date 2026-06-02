"""Unit tests for vessel cashflow comparison presentation."""

from datetime import date

from app.views.compare import build_compare_rows
from vessel_valuation.schema import CashflowYear


def _cashflow_year(year: int, fcf: float) -> CashflowYear:
    period_end = date(2025 + year, 12, 31)
    return CashflowYear(
        year=year,
        period_end=period_end,
        revenue=0.0,
        opex=0.0,
        drydock_capex=0.0,
        upgrades_capex=0.0,
        free_cashflow=fcf,
        net_cashflow=fcf,
        discounted_cashflow=0.0,
        cumulative_cashflow=0.0,
    )


def test_build_compare_rows_aligns_mismatched_lives() -> None:
    """Rows cover the union of years and delta uses zero when a year is missing."""
    schedule_a = [_cashflow_year(0, -100.0), _cashflow_year(1, 10.0)]
    schedule_b = [_cashflow_year(0, -80.0), _cashflow_year(2, 5.0)]

    rows = build_compare_rows(schedule_a, schedule_b)

    assert [row['year'] for row in rows] == [0, 1, 2]
    assert rows[1]['delta'] == '$10'
    assert rows[2]['fcf_a'] == '$0'
