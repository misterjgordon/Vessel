"""View 3 — compare saved valuations (metrics summary + one line item over time)."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import plotly.graph_objects as go
from dash import dash_table
from dash import dcc
from dash import html

from app import component_ids as cid
from app.cashflow_display import CASHFLOW_LINE_ITEMS
from app.cashflow_display import COMPARE_MAX_VESSELS
from app.cashflow_display import COMPARE_MIN_VESSELS
from app.cashflow_display import DEFAULT_COMPARE_METRIC
from app.cashflow_display import cashflow_metric_dropdown_options
from app.cashflow_display import format_money
from app.views.investment import format_irr
from app.views.investment import format_npv
from app.views.investment import format_signal_label

if TYPE_CHECKING:
    from vessel_valuation.schema import ValuationResult


@dataclass(frozen=True)
class CompareVessel:
    """One saved vessel loaded for comparison."""

    vessel_input_id: int
    vessel_name: str
    valuation: ValuationResult


def compare_view() -> html.Div:
    """Build the vessel comparison tab layout."""
    return html.Div(
        [
            html.H3('Compare vessels'),
            html.P(
                'Select 2–20 saved entries (same list as Saved vessels on the Investment tab). '
                'Choose one cashflow line item to overlay across all selected vessels. '
                'Save a valuation first (Calculate, then Save to database).',
                className='help-text',
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label('Saved vessels'),
                            dcc.Dropdown(
                                id=cid.SELECT_COMPARE_VESSELS,
                                options=[],
                                placeholder='Select 2–20 saved vessels',
                                multi=True,
                                clearable=True,
                            ),
                        ],
                        className='compare-select compare-select-wide',
                    ),
                    html.Div(
                        [
                            html.Label('Line item'),
                            dcc.Dropdown(
                                id=cid.SELECT_COMPARE_METRIC,
                                options=cashflow_metric_dropdown_options(),
                                value=DEFAULT_COMPARE_METRIC,
                                clearable=False,
                            ),
                        ],
                        className='compare-select',
                    ),
                ],
                className='compare-select-row',
            ),
            html.Button('Compare', id=cid.BTN_COMPARE, n_clicks=0),
            html.Div(id=cid.COMPARE_PLACEHOLDER, className='placeholder'),
            dash_table.DataTable(
                id=cid.TABLE_COMPARE_SUMMARY,
                columns=compare_summary_columns(),  # ty: ignore[invalid-argument-type]
                data=[],
                page_size=20,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'right', 'padding': '6px'},
                style_header={'fontWeight': 'bold'},
            ),
            dcc.Graph(id=cid.CHART_COMPARE),
            dash_table.DataTable(
                id=cid.TABLE_COMPARE,
                columns=compare_schedule_columns(),  # ty: ignore[invalid-argument-type]
                data=[],
                page_size=30,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'right', 'padding': '6px'},
                style_header={'fontWeight': 'bold'},
            ),
        ],
        className='view-compare',
    )


def compare_summary_columns() -> list[dict[str, str]]:
    """Column definitions for the per-vessel NPV / IRR summary table."""
    return [
        {'name': 'Vessel', 'id': 'vessel'},
        {'name': 'NPV', 'id': 'npv'},
        {'name': 'IRR', 'id': 'irr'},
        {'name': 'Signal', 'id': 'signal'},
    ]


def compare_schedule_columns(
    vessels: list[tuple[int, str]] | None = None,
    metric_label: str = 'Amount',
    *,
    include_delta: bool = False,
) -> list[dict[str, str]]:
    """Column definitions for the year-by-year comparison table."""
    columns: list[dict[str, str]] = [{'name': 'Year', 'id': 'year'}]
    for vessel_input_id, name in vessels or []:
        columns.append(
            {
                'name': f'{name} ({metric_label})',
                'id': _vessel_column_id(vessel_input_id),
            }
        )
    if include_delta:
        columns.append({'name': 'Delta (first − second)', 'id': 'delta'})
    return columns


def build_compare_summary_rows(vessels: list[CompareVessel]) -> list[dict[str, str]]:
    """Build summary table rows with formatted NPV, IRR, and investment signal."""
    rows: list[dict[str, str]] = []
    for entry in vessels:
        irr = entry.valuation.irr
        rows.append(
            {
                'vessel': entry.vessel_name,
                'npv': format_npv(entry.valuation.npv),
                'irr': format_irr(irr),
                'signal': format_signal_label(entry.valuation.investment_signal),
            }
        )
    return rows


def build_compare_schedule_rows(
    vessels: list[CompareVessel],
    field: str,
) -> list[dict[str, str | int]]:
    """Align schedules by year; one column per vessel for the selected line item."""
    by_year: list[dict[int, float]] = []
    for entry in vessels:
        by_year.append(
            {row.year: getattr(row, field) for row in entry.valuation.schedule}
        )
    years = sorted({year for series in by_year for year in series})
    rows: list[dict[str, str | int]] = []
    for year in years:
        record: dict[str, str | int] = {'year': year}
        values: list[float] = []
        for entry, series in zip(vessels, by_year, strict=True):
            value = series.get(year, 0.0)
            values.append(value)
            record[_vessel_column_id(entry.vessel_input_id)] = format_money(value)
        if len(values) == 2:
            record['delta'] = format_money(values[0] - values[1])
        rows.append(record)
    return rows


def compare_chart_title(metric_label: str, vessel_names: list[str]) -> str:
    """Title for the overlay comparison chart."""
    if len(vessel_names) == 2:
        return f'{metric_label} — {vessel_names[0]} vs {vessel_names[1]}'
    return f'{metric_label} — {len(vessel_names)} vessels'


def build_compare_figure(
    vessels: list[CompareVessel],
    field: str,
    metric_label: str,
) -> dict[str, object]:
    """Overlay one cashflow line item across all selected vessels."""
    traces: list[go.Scatter] = []
    all_years: set[int] = set()
    for entry in vessels:
        series = {row.year: getattr(row, field) for row in entry.valuation.schedule}
        all_years.update(series)
    years = sorted(all_years)
    for entry in vessels:
        series = {row.year: getattr(row, field) for row in entry.valuation.schedule}
        y_values = [series.get(year, 0.0) for year in years]
        traces.append(
            go.Scatter(
                x=years,
                y=y_values,
                mode='lines+markers',
                name=entry.vessel_name,
            )
        )
    fig = go.Figure(data=traces)
    names = [entry.vessel_name for entry in vessels]
    fig.update_layout(
        title=compare_chart_title(metric_label, names),
        xaxis_title='Year',
        yaxis_title=f'{metric_label} ($)',
        template='plotly_white',
    )
    return fig.to_dict()


def parse_compare_vessel_selection(
    raw: list[int] | list[str] | int | float | str | None,
) -> tuple[list[int] | None, str]:
    """Validate multi-select vessel ids for compare (count, duplicates)."""
    if raw is None:
        return None, (
            f'Select {COMPARE_MIN_VESSELS}–{COMPARE_MAX_VESSELS} saved vessels.'
        )
    if isinstance(raw, (int, float, str)):
        ids = [int(raw)]
    else:
        ids = [int(vessel_id) for vessel_id in raw]
    unique: list[int] = []
    seen: set[int] = set()
    for vessel_id in ids:
        if vessel_id in seen:
            return None, 'Choose different vessels (no duplicates).'
        seen.add(vessel_id)
        unique.append(vessel_id)
    if len(unique) < COMPARE_MIN_VESSELS:
        return None, (
            f'Select {COMPARE_MIN_VESSELS}–{COMPARE_MAX_VESSELS} saved vessels.'
        )
    if len(unique) > COMPARE_MAX_VESSELS:
        return None, f'At most {COMPARE_MAX_VESSELS} vessels.'
    return unique, ''


def validate_compare_metric(field: str | None) -> str:
    """Return a known schedule field name or the default metric."""
    if field is None:
        return DEFAULT_COMPARE_METRIC
    allowed = {item_field for item_field, _label in CASHFLOW_LINE_ITEMS}
    if field in allowed:
        return field
    return DEFAULT_COMPARE_METRIC


def _vessel_column_id(vessel_input_id: int) -> str:
    return f'vessel_{vessel_input_id}'
