"""View 3 — compare free cash flow across two saved valuations."""

from typing import TYPE_CHECKING

import plotly.graph_objects as go
from dash import dash_table
from dash import dcc
from dash import html

from app import component_ids as cid
from app.views.calculation import _format_money

if TYPE_CHECKING:
    from vessel_valuation.schema import CashflowYear


def compare_view() -> html.Div:
    """Build the vessel comparison tab layout."""
    return html.Div(
        [
            html.H3('Compare cash flows'),
            html.P(
                'Pick any two entries from the database (same list as Saved vessels on '
                'the Investment tab — id, name, TEU, purchase price, and date). '
                'Save a valuation to the database first (Calculate, then Save to database).',
                className='help-text',
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label('Vessel A'),
                            dcc.Dropdown(
                                id=cid.SELECT_COMPARE_A,
                                options=[],
                                placeholder='Choose a saved vessel',
                                clearable=True,
                            ),
                        ],
                        className='compare-select',
                    ),
                    html.Div(
                        [
                            html.Label('Vessel B'),
                            dcc.Dropdown(
                                id=cid.SELECT_COMPARE_B,
                                options=[],
                                placeholder='Choose a saved vessel',
                                clearable=True,
                            ),
                        ],
                        className='compare-select',
                    ),
                ],
                className='compare-select-row',
            ),
            html.Button('Compare', id=cid.BTN_COMPARE, n_clicks=0),
            html.Div(id=cid.COMPARE_PLACEHOLDER, className='placeholder'),
            dcc.Graph(id=cid.CHART_COMPARE),
            dash_table.DataTable(
                id=cid.TABLE_COMPARE,
                columns=compare_table_columns(),  # ty: ignore[invalid-argument-type]
                data=[],
                page_size=30,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'right', 'padding': '6px'},
                style_header={'fontWeight': 'bold'},
            ),
        ],
        className='view-compare',
    )


def compare_table_columns(
    name_a: str = 'Vessel A',
    name_b: str = 'Vessel B',
) -> list[dict[str, str]]:
    """Return DataTable column definitions with vessel names in headers."""
    return [
        {'name': 'Year', 'id': 'year'},
        {'name': f'{name_a} FCF', 'id': 'fcf_a'},
        {'name': f'{name_b} FCF', 'id': 'fcf_b'},
        {'name': 'Delta (A − B)', 'id': 'delta'},
    ]


def build_compare_rows(
    schedule_a: list[CashflowYear],
    schedule_b: list[CashflowYear],
) -> list[dict[str, str | int]]:
    """Align two schedules by year and format FCF cells for the comparison table."""
    by_year_a = {row.year: row for row in schedule_a}
    by_year_b = {row.year: row for row in schedule_b}
    years = sorted(set(by_year_a) | set(by_year_b))
    rows: list[dict[str, str | int]] = []
    for year in years:
        fcf_a = by_year_a[year].free_cashflow if year in by_year_a else 0.0
        fcf_b = by_year_b[year].free_cashflow if year in by_year_b else 0.0
        rows.append(
            {
                'year': year,
                'fcf_a': _format_money(fcf_a),
                'fcf_b': _format_money(fcf_b),
                'delta': _format_money(fcf_a - fcf_b),
            }
        )
    return rows


def compare_chart_title(name_a: str, name_b: str) -> str:
    """Title for the overlay FCF chart."""
    return f'Free cash flow — {name_a} vs {name_b}'


def build_compare_figure(
    name_a: str,
    schedule_a: list[CashflowYear],
    name_b: str,
    schedule_b: list[CashflowYear],
) -> dict[str, object]:
    """Build an overlay line chart of annual free cash flow for two vessels."""
    by_year_a = {row.year: row.free_cashflow for row in schedule_a}
    by_year_b = {row.year: row.free_cashflow for row in schedule_b}
    years = sorted(set(by_year_a) | set(by_year_b))
    fcf_a = [by_year_a.get(year, 0.0) for year in years]
    fcf_b = [by_year_b.get(year, 0.0) for year in years]

    fig = go.Figure(
        data=[
            go.Scatter(x=years, y=fcf_a, mode='lines+markers', name=name_a),
            go.Scatter(x=years, y=fcf_b, mode='lines+markers', name=name_b),
        ]
    )
    fig.update_layout(
        title=compare_chart_title(name_a, name_b),
        xaxis_title='Year',
        yaxis_title='Free cash flow ($)',
        template='plotly_white',
    )
    return fig.to_dict()
