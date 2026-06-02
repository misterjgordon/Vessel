"""View 2 — year-by-year cashflow table (presentation / pivot only)."""

from datetime import date

import plotly.graph_objects as go
from dash import dash_table, dcc, html

from app import component_ids as cid
from vessel_valuation.decision_insights.scenario_schedules import INPUTS_SCENARIO_NAME
from vessel_valuation.schema import CashflowYear

_LINE_ITEMS: tuple[tuple[str, str], ...] = (
    ('revenue', 'Revenue'),
    ('opex', 'OpEx'),
    ('drydock_capex', 'Drydock CapEx'),
    ('upgrades_capex', 'Upgrades CapEx'),
    ('free_cashflow', 'Free cashflow'),
    ('net_cashflow', 'Net cashflow'),
    ('discounted_cashflow', 'Discounted CF'),
    ('cumulative_cashflow', 'Cumulative CF'),
)

_MONEY_FIELDS = frozenset(field for field, _label in _LINE_ITEMS)

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
                columns=empty_dcf_columns(),  # pyright: ignore[reportArgumentType]
                data=[],
                page_size=30,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'right', 'padding': '6px'},
                style_header={'fontWeight': 'bold'},
            ),
            dcc.Graph(
                id=cid.CHART_CASHFLOW,
                figure=empty_cashflow_figure(),
            ),
        ],
        className='view-calculation',
    )


def empty_dcf_columns() -> list[dict[str, str]]:
    """Column definitions when no schedule is loaded."""
    return [{'name': 'Line item', 'id': 'line_item'}]


def empty_cashflow_figure() -> dict[str, object]:
    """Return a placeholder chart before a schedule is available."""
    return _EMPTY_CASHFLOW_FIGURE


def schedule_to_dcf_table(
    schedule: list[CashflowYear],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Pivot schedule into DCF layout: line items as rows, period ends as columns."""
    if not schedule:
        return empty_dcf_columns(), []

    columns: list[dict[str, str]] = [{'name': 'Line item', 'id': 'line_item'}]
    for row in schedule:
        period_id = row.period_end.isoformat()
        columns.append({'name': _format_period_header(row.period_end), 'id': period_id})

    rows: list[dict[str, str]] = []
    for field, label in _LINE_ITEMS:
        record: dict[str, str] = {'line_item': label}
        for row in schedule:
            period_id = row.period_end.isoformat()
            value = getattr(row, field)
            record[period_id] = _format_cell(field, value)
        rows.append(record)
    return columns, rows


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
        for field, label in _LINE_ITEMS
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


def _format_period_header(period_end: date) -> str:
    return period_end.strftime('%d %b %Y')


def _format_cell(field: str, value: float) -> str:
    if field in _MONEY_FIELDS:
        return _format_money(value)
    return str(value)


def _format_money(value: float) -> str:
    sign = '-' if value < 0 else ''
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f'{sign}${absolute / 1_000_000:,.2f}m'
    if absolute >= 1_000:
        return f'{sign}${absolute / 1_000:,.1f}k'
    return f'{sign}${absolute:,.0f}'
