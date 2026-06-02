"""Unit tests for calculation detail cashflow presentation."""

from datetime import date

from app.views.calculation import (
    build_cashflow_chart_figure,
    schedule_to_dcf_table,
)
from vessel_valuation.schema import CashflowYear


def _cashflow_year(year: int, revenue: float) -> CashflowYear:
    period_end = date(2025 + year, 12, 31)
    return CashflowYear(
        year=year,
        period_end=period_end,
        revenue=revenue,
        opex=-1.0,
        drydock_capex=0.0,
        upgrades_capex=0.0,
        free_cashflow=revenue - 1.0,
        net_cashflow=revenue - 1.0,
        discounted_cashflow=0.0,
        cumulative_cashflow=0.0,
    )


def test_schedule_to_dcf_table_pivots_periods_as_columns() -> None:
    """Line items are rows and period-end dates are column headers."""
    schedule = [_cashflow_year(0, 100.0), _cashflow_year(1, 200.0)]

    columns, rows = schedule_to_dcf_table(schedule)

    assert columns[0]['id'] == 'line_item'
    assert [col['id'] for col in columns[1:]] == ['2025-12-31', '2026-12-31']
    assert columns[1]['name'] == '31 Dec 2025'
    revenue_row = next(row for row in rows if row['line_item'] == 'Revenue')
    assert revenue_row['2025-12-31'] == '$100'
    assert revenue_row['2026-12-31'] == '$200'


def test_build_cashflow_chart_figure_includes_all_line_items() -> None:
    """Chart has one trace per cashflow line item."""
    schedule = [_cashflow_year(0, 50.0), _cashflow_year(1, 60.0)]

    figure = build_cashflow_chart_figure(schedule)

    assert len(figure['data']) == 8
