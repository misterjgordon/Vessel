"""Investment, calculation, and compare view render callbacks."""

from typing import TYPE_CHECKING
from typing import cast

from dash import Dash
from dash import html
from dash.exceptions import PreventUpdate
from dash.dependencies import Input
from dash.dependencies import Output
from dash.dependencies import State

from app import component_ids as cid
from app.callbacks._debug_log import agent_debug_log
from app.callbacks._helpers import EMPTY_COMPARE_FIGURE
from app.callbacks._helpers import calculation_schedules
from app.callbacks._helpers import sensitivity_figure
from app.callbacks._helpers import signal_css_class
from app.views.calculation import build_cashflow_chart_figure
from app.views.calculation import empty_cashflow_figure
from app.views.calculation import schedule_to_long_table
from app.cashflow_display import cashflow_line_item_label
from app.views.compare import CompareVessel
from app.views.compare import build_compare_figure
from app.views.compare import build_compare_schedule_rows
from app.views.compare import build_compare_summary_rows
from app.views.compare import parse_compare_vessel_selection
from app.views.compare import validate_compare_metric
from app.views.investment import format_irr
from app.views.investment import format_npv
from app.views.investment import format_payback_year
from app.views.investment import format_rate_per_day
from app.views.investment import format_signal_label
from app.views.investment import scenario_table_rows
from vessel_valuation.db.connection import session_scope
from vessel_valuation.db.repository import get_valuation
from vessel_valuation.db.repository import get_vessel_inputs
from vessel_valuation.serialize import json_float
from vessel_valuation.serialize import scenario_bundles_from_json

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from sqlalchemy.orm import sessionmaker

def register(app: Dash, session_factory: sessionmaker[Session]) -> None:
    """Register view render callbacks."""

    def _empty_compare_outputs(
        message: str = '',
    ) -> tuple[object, object, object, object]:
        return (
            [],
            EMPTY_COMPARE_FIGURE,
            [],
            message,
        )

    @app.callback(
        Output(cid.TABLE_COMPARE_SUMMARY, 'data'),
        Output(cid.CHART_COMPARE, 'figure'),
        Output(cid.TABLE_COMPARE, 'data'),
        Output(cid.COMPARE_PLACEHOLDER, 'children'),
        Input(cid.APP_TABS, 'value'),
        Input(cid.BTN_COMPARE, 'n_clicks'),
        Input(cid.SELECT_COMPARE_METRIC, 'value'),
        State(cid.SELECT_COMPARE_VESSELS, 'value'),
        prevent_initial_call=True,
    )
    def on_compare_vessels(
        active_tab: str | None,
        n_clicks: int | None,
        metric_field: str | None,
        vessel_ids_raw: list[int] | list[str] | int | float | str | None,
    ) -> tuple[object, object, object, object]:
        """Summary metrics plus one schedule line item across selected saved valuations."""
        if active_tab != cid.TAB_VALUE_COMPARE:
            raise PreventUpdate
        # region agent log
        agent_debug_log(
            location='render.py:on_compare_vessels:entry',
            message='on_compare_vessels invoked',
            data={'n_clicks': n_clicks, 'metric_field': metric_field},
            hypothesis_id='H2',
            run_id='post-fix',
        )
        # endregion
        if not n_clicks:
            return _empty_compare_outputs()

        vessel_ids, selection_message = parse_compare_vessel_selection(vessel_ids_raw)
        if vessel_ids is None:
            return _empty_compare_outputs(selection_message)

        field = validate_compare_metric(metric_field)
        metric_label = cashflow_line_item_label(field)

        entries: list[CompareVessel] = []
        with session_scope(session_factory) as session:
            for vessel_input_id in vessel_ids:
                inputs = get_vessel_inputs(session, vessel_input_id)
                valuation = get_valuation(session, vessel_input_id)
                if inputs is None:
                    return _empty_compare_outputs(
                        'One or more saved vessels were not found.',
                    )
                if valuation is None:
                    return _empty_compare_outputs(
                        'Every selected vessel needs a saved valuation '
                        '(run Calculate first).',
                    )
                entries.append(
                    CompareVessel(
                        vessel_input_id=vessel_input_id,
                        vessel_name=inputs.vessel_name,
                        valuation=valuation,
                    )
                )

        figure = build_compare_figure(entries, field, metric_label)
        summary_rows = build_compare_summary_rows(entries)
        schedule_rows = build_compare_schedule_rows(entries, field)
        return (
            summary_rows,
            figure,
            schedule_rows,
            '',
        )

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
        # region agent log
        agent_debug_log(
            location='render.py:render_investment_results:entry',
            message='render_investment_results invoked',
            data={
                'has_store': store is not None,
                'has_valuation': bool(store and 'valuation' in store),
            },
            hypothesis_id='H5',
        )
        # endregion
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

        valuation_raw = store['valuation']
        assert isinstance(valuation_raw, dict)
        valuation = cast('dict[str, object]', valuation_raw)
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

        sensitivity_raw = valuation['sensitivity']
        assert isinstance(sensitivity_raw, list)
        figure = sensitivity_figure(cast('list[dict[str, object]]', sensitivity_raw))

        scenarios_raw = valuation['scenarios']
        assert isinstance(scenarios_raw, dict)
        scenarios = cast('dict[str, dict[str, object]]', scenarios_raw)
        bundles_raw = store.get('scenario_bundles')
        bundles = (
            scenario_bundles_from_json(cast('list[dict[str, object]]', bundles_raw))
            if isinstance(bundles_raw, list)
            else None
        )
        scenarios_rows = scenario_table_rows(scenarios, bundles=bundles)
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
        Output(cid.TABLE_CASHFLOW, 'data'),
        Output(cid.CHART_CASHFLOW, 'figure'),
        Output(cid.CALCULATION_PLACEHOLDER, 'children'),
        Input(cid.APP_TABS, 'value'),
        Input(cid.SELECT_SCENARIO, 'value'),
        Input(cid.STORE_COMPUTE, 'data'),
        Input(cid.SELECT_CALCULATION_VESSEL, 'value'),
    )
    def render_cashflow_detail(
        active_tab: str | None,
        scenario: str | None,
        store: dict[str, object] | None,
        calculation_vessel_id: int | None,
    ) -> tuple[object, object, object]:
        """Render DCF pivot table and trend chart from session store or database entry."""
        # region agent log
        agent_debug_log(
            location='render.py:render_cashflow_detail:entry',
            message='render_cashflow_detail invoked',
            data={
                'active_tab': active_tab,
                'scenario': scenario,
                'has_store': store is not None,
                'calculation_vessel_id': calculation_vessel_id,
            },
            hypothesis_id='H1',
            run_id='post-fix',
        )
        # endregion
        if active_tab != cid.TAB_VALUE_CALCULATION:
            raise PreventUpdate
        if scenario is None:
            return (
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
            return [], empty_cashflow_figure(), placeholder

        schedule = schedules.get(scenario, [])
        rows = schedule_to_long_table(schedule)
        figure = build_cashflow_chart_figure(schedule)
        # region agent log
        agent_debug_log(
            location='render.py:render_cashflow_detail:success',
            message='render_cashflow_detail returning table and chart',
            data={'row_count': len(rows)},
            hypothesis_id='H1',
            run_id='post-fix',
        )
        # endregion
        return rows, figure, placeholder
