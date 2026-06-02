"""Investment, calculation, and compare view render callbacks."""

from dash import Dash, html
from dash.dependencies import Input, Output, State
from sqlalchemy.orm import Session, sessionmaker

from app import component_ids as cid
from app.callbacks._helpers import (
    EMPTY_COMPARE_FIGURE,
    calculation_schedules,
    sensitivity_figure,
    signal_css_class,
)
from vessel_valuation.serialize import json_float
from app.views.calculation import (
    build_cashflow_chart_figure,
    empty_cashflow_figure,
    empty_dcf_columns,
    schedule_to_dcf_table,
)
from app.views.compare import (
    build_compare_figure,
    build_compare_rows,
    compare_table_columns,
)
from app.views.investment import (
    format_irr,
    format_npv,
    format_payback_year,
    format_rate_per_day,
    format_signal_label,
    scenario_table_rows,
)
from vessel_valuation.db.connection import session_scope
from vessel_valuation.db.repository import get_valuation, get_vessel_inputs


def register(app: Dash, session_factory: sessionmaker[Session]) -> None:
    """Register view render callbacks."""

    @app.callback(
        Output(cid.CHART_COMPARE, 'figure'),
        Output(cid.TABLE_COMPARE, 'columns'),
        Output(cid.TABLE_COMPARE, 'data'),
        Output(cid.COMPARE_PLACEHOLDER, 'children'),
        Input(cid.BTN_COMPARE, 'n_clicks'),
        State(cid.SELECT_COMPARE_A, 'value'),
        State(cid.SELECT_COMPARE_B, 'value'),
        prevent_initial_call=True,
    )
    def on_compare_vessels(
        n_clicks: int | None,
        vessel_a_id: int | None,
        vessel_b_id: int | None,
    ) -> tuple[object, object, object, object]:
        """Overlay and tabulate free cash flow for two saved valuations."""
        if not n_clicks:
            return EMPTY_COMPARE_FIGURE, compare_table_columns(), [], ''

        if vessel_a_id is None or vessel_b_id is None:
            return (
                EMPTY_COMPARE_FIGURE,
                compare_table_columns(),
                [],
                'Select two saved vessels.',
            )
        if vessel_a_id == vessel_b_id:
            return (
                EMPTY_COMPARE_FIGURE,
                compare_table_columns(),
                [],
                'Choose two different vessels to compare.',
            )

        with session_scope(session_factory) as session:
            inputs_a = get_vessel_inputs(session, vessel_a_id)
            inputs_b = get_vessel_inputs(session, vessel_b_id)
            valuation_a = get_valuation(session, vessel_a_id)
            valuation_b = get_valuation(session, vessel_b_id)

        if inputs_a is None or inputs_b is None:
            return (
                EMPTY_COMPARE_FIGURE,
                compare_table_columns(),
                [],
                'One or both saved vessels were not found.',
            )
        if valuation_a is None or valuation_b is None:
            return (
                EMPTY_COMPARE_FIGURE,
                compare_table_columns(),
                [],
                'Both vessels need a saved valuation (run Calculate first).',
            )

        name_a = inputs_a.vessel_name
        name_b = inputs_b.vessel_name
        figure = build_compare_figure(
            name_a,
            valuation_a.schedule,
            name_b,
            valuation_b.schedule,
        )
        table_rows = build_compare_rows(valuation_a.schedule, valuation_b.schedule)
        columns = compare_table_columns(name_a, name_b)
        return figure, columns, table_rows, ''

    @app.callback(
        Output(cid.CARD_NPV, 'children'),
        Output(cid.CARD_IRR, 'children'),
        Output(cid.CARD_SIGNAL, 'children'),
        Output(cid.CARD_BREAKEVEN, 'children'),
        Output(cid.CARD_PAYBACK, 'children'),
        Output(cid.TABLE_SCENARIOS, 'data'),
        Output(cid.CHART_SENSITIVITY, 'figure'),
        Input(cid.STORE_COMPUTE, 'data'),
    )
    def render_investment_results(
        store: dict[str, object] | None,
    ) -> tuple[object, object, object, object, object, object, object]:
        """Render View 1 outputs from the compute store."""
        empty = '—'
        empty_figure: dict[str, object] = {
            'data': [],
            'layout': {'title': 'Run a valuation to see sensitivity'},
        }
        if store is None or 'valuation' not in store:
            return (
                empty,
                empty,
                empty,
                empty,
                empty,
                scenario_table_rows(),
                empty_figure,
            )

        valuation = store['valuation']
        assert isinstance(valuation, dict)
        npv = json_float(valuation['npv'], 'npv')
        irr_raw = valuation['irr']
        irr = json_float(valuation['irr'], 'irr') if irr_raw is not None else None
        signal = str(valuation['investment_signal'])
        breakeven_raw = valuation['breakeven_rate']
        breakeven = (
            json_float(valuation['breakeven_rate'], 'breakeven_rate')
            if breakeven_raw is not None
            else None
        )
        payback_raw = valuation.get('payback_year')
        payback: int | None = None
        if isinstance(payback_raw, int):
            payback = payback_raw
        elif isinstance(payback_raw, float):
            payback = int(payback_raw)

        sensitivity = valuation['sensitivity']
        assert isinstance(sensitivity, list)
        figure = sensitivity_figure(sensitivity)

        scenarios = valuation['scenarios']
        assert isinstance(scenarios, dict)
        scenarios_rows = scenario_table_rows(scenarios)
        signal_css = signal_css_class(signal)

        return (
            format_npv(npv),
            format_irr(irr),
            html.Span(format_signal_label(signal), className=signal_css),
            format_rate_per_day(breakeven),
            format_payback_year(payback),
            scenarios_rows,
            figure,
        )

    @app.callback(
        Output(cid.TABLE_CASHFLOW, 'columns'),
        Output(cid.TABLE_CASHFLOW, 'data'),
        Output(cid.CHART_CASHFLOW, 'figure'),
        Output(cid.CALCULATION_PLACEHOLDER, 'children'),
        Input(cid.SELECT_SCENARIO, 'value'),
        Input(cid.STORE_COMPUTE, 'data'),
        Input(cid.SELECT_CALCULATION_VESSEL, 'value'),
    )
    def render_cashflow_detail(
        scenario: str | None,
        store: dict[str, object] | None,
        calculation_vessel_id: int | None,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object], str]:
        """Render DCF pivot table and trend chart from session store or database entry."""
        if scenario is None:
            return (
                empty_dcf_columns(),
                [],
                empty_cashflow_figure(),
                'Select a scenario to view the schedule.',
            )

        schedules, placeholder = calculation_schedules(
            session_factory,
            store,
            calculation_vessel_id,
        )
        if schedules is None:
            return empty_dcf_columns(), [], empty_cashflow_figure(), placeholder

        schedule = schedules.get(scenario, [])
        columns, rows = schedule_to_dcf_table(schedule)
        figure = build_cashflow_chart_figure(schedule)
        return columns, rows, figure, placeholder
