"""View 2 — year-by-year cashflow table (presentation / pivot only)."""

from typing import TYPE_CHECKING

import plotly.graph_objects as go
from dash import dash_table
from dash import dcc
from dash import html

from app import component_ids as cid
from app.cashflow_display import CASHFLOW_LINE_ITEMS
from app.table_styles import DATA_TABLE_CELL_STYLE
from app.table_styles import DATA_TABLE_HEADER_STYLE
from app.table_styles import DATA_TABLE_STYLE_TABLE
from app.table_styles import data_table_left_align
from app.cashflow_display import CASHFLOW_MONEY_FIELDS
from app.cashflow_display import format_money
from app.cashflow_display import format_period_header
from vessel_valuation.decision_insights.scenario_schedules import INPUTS_SCENARIO_NAME

if TYPE_CHECKING:
    from vessel_valuation.schema import CashflowYear

_EMPTY_CASHFLOW_FIGURE: dict[str, object] = {
    'data': [],
    'layout': {'title': 'Run Calculate or select a saved entry'},
}


def calculation_view() -> html.Div:
    """Build the calculation detail tab layout."""
    scenario_options = [
        {'label': INPUTS_SCENARIO_NAME, 'value': INPUTS_SCENARIO_NAME},
        {'label': 'Best', 'value': 'Best'},
        {'label': 'Base', 'value': 'Base'},
        {'label': 'Worst', 'value': 'Worst'},
    ]
    return html.Div(
        [
            html.H3('Year-by-year cash flow'),
            html.P(
                'Uses the active valuation from the Investment tab when available. '
                'Otherwise choose any saved database entry (same ids as Saved vessels). '
                'Selecting an entry here loads all scenarios for that vessel.',
                className='help-text',
            ),
            html.Div(
                [
                    html.Label('Saved entry (optional)'),
                    dcc.Dropdown(
                        id=cid.SELECT_CALCULATION_VESSEL,
                        options=[],
                        placeholder='Select to load from database',
                        clearable=True,
                    ),
                ],
                className='calculation-vessel-select',
            ),
            html.Div(
                [
                    html.Label('Scenario'),
                    dcc.Dropdown(
                        id=cid.SELECT_SCENARIO,
                        options=scenario_options,
                        value=INPUTS_SCENARIO_NAME,
                        clearable=False,
                    ),
                ],
                className='scenario-select',
            ),
            html.Div(id=cid.CALCULATION_PLACEHOLDER, className='placeholder'),
            dash_table.DataTable(
                id=cid.TABLE_CASHFLOW,
                columns=cashflow_table_columns(),  # ty: ignore[invalid-argument-type]
                data=[],
                page_size=30,
                style_table=DATA_TABLE_STYLE_TABLE,
                style_cell=DATA_TABLE_CELL_STYLE,
                style_cell_conditional=[data_table_left_align('line_item')],  # ty: ignore[invalid-argument-type]
                style_header=DATA_TABLE_HEADER_STYLE,
            ),
            dcc.Graph(
                id=cid.CHART_CASHFLOW,
                figure=empty_cashflow_figure(),
            ),
        ],
        className='view-calculation',
    )


def cashflow_table_columns() -> list[dict[str, str]]:
    """Fixed column definitions for the cashflow detail table (long format)."""
    return [
        {'name': 'Line item', 'id': 'line_item'},
        {'name': 'Period end', 'id': 'period_end'},
        {'name': 'Amount', 'id': 'amount'},
    ]


def empty_dcf_columns() -> list[dict[str, str]]:
    """Alias for layout wiring; columns are fixed in long format."""
    return cashflow_table_columns()


def empty_cashflow_figure() -> dict[str, object]:
    """Return a placeholder chart before a schedule is available."""
    return _EMPTY_CASHFLOW_FIGURE


def schedule_to_long_table(schedule: list[CashflowYear]) -> list[dict[str, str]]:
    """One row per line item and period; avoids dynamic DataTable columns in callbacks."""
    if not schedule:
        return []

    rows: list[dict[str, str]] = []
    for field, label in CASHFLOW_LINE_ITEMS:
        for row in schedule:
            rows.append(
                {
                    'line_item': label,
                    'period_end': format_period_header(row.period_end),
                    'amount': _format_cell(field, getattr(row, field)),
                }
            )
    return rows


def build_cashflow_chart_figure(schedule: list[CashflowYear]) -> dict[str, object]:
    """Line chart of each cashflow line item vs period end."""
    if not schedule:
        return empty_cashflow_figure()

    period_ends = [row.period_end for row in schedule]
    traces = [
        go.Scatter(
            x=period_ends,
            y=[getattr(row, field) for row in schedule],
            mode='lines+markers',
            name=label,
        )
        for field, label in CASHFLOW_LINE_ITEMS
    ]
    fig = go.Figure(data=traces)
    fig.update_layout(
        title='Cash flows by period end',
        xaxis_title='Period end',
        yaxis_title='Amount ($)',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    return fig.to_dict()


def _format_cell(field: str, value: float) -> str:
    if field in CASHFLOW_MONEY_FIELDS:
        return format_money(value)
    return str(value)
