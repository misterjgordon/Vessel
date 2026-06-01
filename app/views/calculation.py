"""View 2 — year-by-year cashflow table (presentation / pivot only)."""

from dash import dash_table, dcc, html

from app import component_ids as cid
from vessel_valuation.decision_insights.scenario_schedules import INPUTS_SCENARIO_NAME
from vessel_valuation.schema import CashflowYear

_TABLE_COLUMNS: tuple[tuple[str, str], ...] = (
    ('year', 'Year'),
    ('period_end', 'Period end'),
    ('revenue', 'Revenue'),
    ('opex', 'OpEx'),
    ('drydock_capex', 'Drydock CapEx'),
    ('upgrades_capex', 'Upgrades CapEx'),
    ('free_cashflow', 'Free cashflow'),
    ('net_cashflow', 'Net cashflow'),
    ('discounted_cashflow', 'Discounted CF'),
    ('cumulative_cashflow', 'Cumulative CF'),
)

_MONEY_FIELDS = frozenset(
    {
        'revenue',
        'opex',
        'drydock_capex',
        'upgrades_capex',
        'free_cashflow',
        'net_cashflow',
        'discounted_cashflow',
        'cumulative_cashflow',
    }
)


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
                columns=datatable_columns(),  # pyright: ignore[reportArgumentType]
                data=[],
                page_size=30,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'right', 'padding': '6px'},
                style_header={'fontWeight': 'bold'},
            ),
        ],
        className='view-calculation',
    )


def datatable_columns() -> list[dict[str, str]]:
    """Return DataTable column definitions."""
    return [{'name': label, 'id': field} for field, label in _TABLE_COLUMNS]


def schedule_to_rows(schedule: list[CashflowYear]) -> list[dict[str, str | int]]:
    """Pivot a schedule into DataTable rows (years on the Y-axis)."""
    rows: list[dict[str, str | int]] = []
    for row in schedule:
        record: dict[str, str | int] = {'year': row.year}
        record['period_end'] = row.period_end.isoformat()
        for field, _label in _TABLE_COLUMNS:
            if field in ('year', 'period_end'):
                continue
            value = getattr(row, field)
            record[field] = _format_cell(field, value)
        rows.append(record)
    return rows


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
