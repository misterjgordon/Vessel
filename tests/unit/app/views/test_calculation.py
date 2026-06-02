"""Unit tests for calculation detail cashflow presentation."""

from datetime import date

from app.views.calculation import build_cashflow_chart_figure
from app.views.calculation import schedule_to_long_table
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


def test_schedule_to_long_table_lists_each_line_item_and_period() -> None:
    """Each line item and period end is its own row with a formatted amount."""
    schedule = [_cashflow_year(0, 100.0), _cashflow_year(1, 200.0)]

    rows = schedule_to_long_table(schedule)

    revenue_rows = [row for row in rows if row['line_item'] == 'Revenue']
    assert len(revenue_rows) == 2
    assert revenue_rows[0]['period_end'] == '31 Dec 2025'
    assert revenue_rows[0]['amount'] == '$100'
    assert revenue_rows[1]['amount'] == '$200'


def test_build_cashflow_chart_figure_includes_all_line_items() -> None:
    """Chart has one trace per cashflow line item."""
    schedule = [_cashflow_year(0, 50.0), _cashflow_year(1, 60.0)]

    figure = build_cashflow_chart_figure(schedule)

    traces = figure['data']
    assert isinstance(traces, list)
    assert len(traces) == 8
