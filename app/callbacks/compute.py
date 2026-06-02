"""Calculate valuation callback."""

from typing import TYPE_CHECKING

from dash import Dash
from dash import no_update
from dash.dependencies import Input
from dash.dependencies import Output
from dash.dependencies import State

from app import component_ids as cid
from app.callbacks._helpers import FORM_NO_UPDATES
from app.callbacks._helpers import LOAD_FORM_OUTPUTS
from app.callbacks._helpers import build_compute_store
from app.callbacks._helpers import form_values_tuple
from app.callbacks._helpers import optional_float
from app.serialization import form_values_to_raw
from app.views.investment import collect_form_values
from vessel_valuation.db.connection import session_scope
from vessel_valuation.db.repository import list_fleet_vessel_inputs
from vessel_valuation.decision_insights.enrich import enrich
from vessel_valuation.decision_insights.scenario_bundles import resolve_scenario_bundles
from vessel_valuation.decision_insights.scenario_schedules import scenario_schedules
from vessel_valuation.file_parser import pp_teu_factor_benchmarks_for_subject
from vessel_valuation.validation import validate

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from sqlalchemy.orm import sessionmaker


def register(app: Dash, session_factory: sessionmaker[Session]) -> None:
    """Register the Calculate valuation callback."""

    @app.callback(
        Output(cid.STORE_COMPUTE, 'data'),
        Output(cid.BANNER_VALIDATION, 'children'),
        Output(cid.BANNER_VALIDATION, 'className'),
        *LOAD_FORM_OUTPUTS,
        Input(cid.BTN_CALCULATE, 'n_clicks'),
        State(cid.INPUT_REV_MIN, 'value'),
        State(cid.INPUT_REV_MAX, 'value'),
        # Scenario table must precede form fields: handler uses *form_values last.
        State(cid.TABLE_SCENARIOS, 'data'),
        State(cid.INPUT_VESSEL_NAME, 'value'),
        State(cid.INPUT_PURCHASE_PRICE, 'value'),
        State(cid.INPUT_VESSEL_LIFE, 'value'),
        State(cid.INPUT_RESIDUAL_VALUE, 'value'),
        State(cid.INPUT_LW_TONNAGE, 'value'),
        State(cid.INPUT_REVENUE_PER_DAY, 'value'),
        State(cid.INPUT_OFFHIRE_RATE, 'value'),
        State(cid.INPUT_OPEX_PER_DAY, 'value'),
        State(cid.INPUT_DRYDOCK_CAPEX, 'value'),
        State(cid.INPUT_DRYDOCK_FREQUENCY, 'value'),
        State(cid.INPUT_UPGRADES_CAPEX, 'value'),
        State(cid.INPUT_INFLATION_RATE, 'value'),
        State(cid.INPUT_DISCOUNT_RATE, 'value'),
        State(cid.INPUT_DAYS_OF_YEAR, 'value'),
        State(cid.INPUT_TEU_SIZE, 'value'),
        State(cid.INPUT_PURCHASE_DATE, 'value'),
        State(cid.INPUT_ENGINE_TYPE, 'value'),
        State(cid.INPUT_CO2_CARBON_FACTOR, 'value'),
        prevent_initial_call=True,
    )
    def on_calculate(
        n_clicks: int | None,
        rev_min: float | None,
        rev_max: float | None,
        scenario_table_data: list[dict[str, object]] | None,
        *form_values: str | int | float | None,
    ) -> tuple[object, ...]:
        """Validate inputs, enrich in memory, and store results for both views."""
        if not n_clicks:
            return (no_update, no_update, no_update, *FORM_NO_UPDATES)

        form = collect_form_values(*form_values)
        raw_payload = form_values_to_raw(form)

        rev_min_val = optional_float(rev_min)
        rev_max_val = optional_float(rev_max)

        try:
            scenario_bundles, scenario_warnings = resolve_scenario_bundles(scenario_table_data)
        except ValueError as exc:
            return no_update, str(exc), 'validation-banner error', *FORM_NO_UPDATES

        with session_scope(session_factory) as session:
            fleet_peers = list_fleet_vessel_inputs(session)
            validation = validate(raw_payload)
            if validation.inputs is None:
                message = '; '.join(validation.errors) if validation.errors else 'Validation failed'
                return no_update, message, 'validation-banner error', *FORM_NO_UPDATES

            factor_benchmarks = pp_teu_factor_benchmarks_for_subject(
                fleet_peers,
                validation.inputs,
            )
            validation = validate(
                raw_payload,
                pp_teu_factor_benchmarks=factor_benchmarks if factor_benchmarks else None,
            )
            inputs = validation.inputs
            assert inputs is not None
            result = enrich(
                inputs,
                bundles=scenario_bundles,
                rev_min=rev_min_val,
                rev_max=rev_max_val,
            )

        warnings = list(validation.warnings)
        warnings.extend(scenario_warnings)
        source = 'manual_form'
        schedules = scenario_schedules(inputs, bundles=scenario_bundles)
        store_data = build_compute_store(
            inputs=inputs,
            result=result,
            schedules=schedules,
            scenario_bundles=scenario_bundles,
            warnings=warnings,
            raw_payload=raw_payload,
            source=source,
            rev_min=rev_min_val,
            rev_max=rev_max_val,
        )

        form_tuple = form_values_tuple(inputs)
        banner_class = 'validation-banner warning' if warnings else 'validation-banner ok'
        if warnings:
            banner_text = (
                f'Valuation computed for {inputs.vessel_name} (not saved). '
                f'Warnings: {"; ".join(warnings)}. Click Save to database to persist.'
            )
        else:
            banner_text = (
                f'Valuation computed for {inputs.vessel_name}. '
                'Click Save to database to persist for Compare.'
            )
        return store_data, banner_text, banner_class, *form_tuple
