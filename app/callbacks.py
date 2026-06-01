"""Dash callbacks — thin wiring to validation, repository, and decision insights."""

import base64

import plotly.graph_objects as go
from dash import Dash, html, no_update
from dash.dependencies import Input, Output, State
from sqlalchemy.orm import Session, sessionmaker

from app import component_ids as cid
from app.serialization import (
    _float_field,
    form_values_to_raw,
    schedules_from_store,
    schedules_to_store,
    valuation_to_store,
    vessel_inputs_from_store,
    vessel_inputs_to_form_values,
    vessel_inputs_to_store,
)
from app.views.calculation import schedule_to_rows
from app.views.compare import (
    build_compare_figure,
    build_compare_rows,
    compare_table_columns,
)
from app.form_defaults import FORM_DEFAULTS
from app.form_formatting import format_form_field_value
from app.views.investment import (
    FORM_COMPONENT_IDS,
    FORM_FIELD_NAMES,
    INPUT_SOURCE_BTN_ACTIVE_CLASS,
    INPUT_SOURCE_BTN_CLASS,
    MODAL_HIDDEN_CLASS,
    MODAL_OPEN_CLASS,
    collect_form_values,
    executive_summary_panel,
    format_irr,
    format_metadata,
    format_npv,
    format_payback_year,
    format_rate_per_day,
    format_saved_vessel_option_label,
    format_signal_label,
    scenario_summary_table,
)
from vessel_valuation.db.connection import session_scope
from vessel_valuation.db.repository import (
    delete_vessel_inputs,
    get_valuation,
    get_vessel_inputs,
    list_fleet_vessel_inputs,
    list_vessels,
    load_pp_teu_factor_benchmarks,
    persist_vessel_submission,
)
from vessel_valuation.decision_insights.enrich import enrich
from vessel_valuation.decision_insights.scenario_schedules import scenario_schedules
from vessel_valuation.schema import CashflowYear, ValuationResult, VesselInputs
from vessel_valuation.file_parser import parse_upload, pp_teu_factor_benchmarks_for_subject
from vessel_valuation.validation import validate

_LOAD_FORM_OUTPUTS = [Output(component_id, 'value') for component_id in FORM_COMPONENT_IDS]
_LOAD_FORM_OUTPUTS_DUPLICATE = [
    Output(component_id, 'value', allow_duplicate=True) for component_id in FORM_COMPONENT_IDS
]
_FORM_NO_UPDATES = (no_update,) * len(FORM_COMPONENT_IDS)

_EMPTY_COMPARE_FIGURE: dict[str, object] = {
    'data': [],
    'layout': {'title': 'Select two vessels and click Compare'},
}


def _normalize_vessel_input_ids(
    raw: list[int] | list[str] | int | float | str | None,
) -> list[int]:
    """Coerce saved-vessel dropdown value(s) to a list of integer ids.

    Dash may send a bare int for a single multi-select choice; repository delete
    expects a list.
    """
    if raw is None:
        return []
    if isinstance(raw, (int, float, str)):
        return [int(raw)]
    return [int(vessel_input_id) for vessel_input_id in raw]


def register_callbacks(app: Dash, session_factory: sessionmaker[Session]) -> None:
    """Register all application callbacks on ``app``."""

    @app.callback(
        Output(cid.STORE_UPLOAD, 'data'),
        Output(cid.UPLOAD_SUMMARY_TABLE, 'data'),
        Output(cid.UPLOAD_SUMMARY_TABLE, 'selected_rows'),
        Output(cid.STORE_UPLOAD_SELECTED_ROW, 'data'),
        Output(cid.UPLOAD_SELECTION_LABEL, 'children'),
        Output(cid.MODAL_UPLOAD, 'className'),
        Output(cid.STORE_ACTIVE_INPUT_SOURCE, 'data', allow_duplicate=True),
        Input(cid.UPLOAD_FILE, 'contents'),
        State(cid.UPLOAD_FILE, 'filename'),
        prevent_initial_call=True,
    )
    def on_file_upload(
        contents: str | None,
        filename: str | None,
    ) -> tuple[
        object,
        object,
        object,
        object,
        object,
        object,
        object,
    ]:
        """Parse an uploaded file and populate the row summary table."""
        if contents is None or filename is None:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update

        _content_type, content_string = contents.split(',', 1)
        raw_bytes = base64.b64decode(content_string)
        with session_scope(session_factory) as session:
            fleet_peers = list_fleet_vessel_inputs(session)
        parse_result = parse_upload(raw_bytes, filename, fleet_peer_inputs=fleet_peers)

        if not parse_result.ok:
            message = '; '.join(parse_result.header_errors)
            table_row = {
                'row_number': 0,
                'vessel_name': '',
                'teu_size': '',
                'purchase_price': '',
                'status': 'error',
                'messages': message,
            }
            return (
                None,
                [table_row],
                [],
                None,
                'Fix header errors above, then re-upload.',
                MODAL_OPEN_CLASS,
                'file',
            )

        upload_rows: list[dict[str, object]] = []
        table_data: list[dict[str, str | int]] = []

        for row in parse_result.rows:
            if row.errors:
                status = 'error'
            elif row.warnings:
                status = 'warning'
            else:
                status = 'ok'
            messages = '; '.join(row.errors + row.warnings)
            upload_rows.append(
                {
                    'row_number': row.row_number,
                    'raw': row.raw,
                    'errors': row.errors,
                    'warnings': row.warnings,
                }
            )
            table_data.append(
                {
                    **_upload_preview_row(row.row_number, row.raw),
                    'status': status,
                    'messages': messages,
                }
            )
        store_payload: dict[str, object] = {'rows': upload_rows}
        return (
            store_payload,
            table_data,
            [],
            None,
            'Click a row to load it into the vessel form.',
            MODAL_OPEN_CLASS,
            'file',
        )

    @app.callback(
        Output(cid.MODAL_UPLOAD, 'className', allow_duplicate=True),
        Input(cid.BTN_MODAL_UPLOAD_CLOSE, 'n_clicks'),
        prevent_initial_call=True,
    )
    def close_upload_modal(_n_clicks: int | None) -> str:
        """Dismiss the file-upload picker."""
        return MODAL_HIDDEN_CLASS

    @app.callback(
        Output(cid.MODAL_DATABASE, 'className'),
        Input(cid.BTN_INPUT_OPTION_DATABASE, 'n_clicks'),
        prevent_initial_call=True,
    )
    def open_database_modal(_n_clicks: int | None) -> str:
        """Show the saved-vessel picker."""
        return MODAL_OPEN_CLASS

    @app.callback(
        Output(cid.MODAL_DATABASE, 'className', allow_duplicate=True),
        Input(cid.BTN_MODAL_DATABASE_CLOSE, 'n_clicks'),
        Input(cid.BTN_MODAL_DATABASE_CANCEL, 'n_clicks'),
        prevent_initial_call=True,
    )
    def close_database_modal(
        _close_clicks: int | None,
        _cancel_clicks: int | None,
    ) -> str:
        """Dismiss the database picker."""
        return MODAL_HIDDEN_CLASS

    @app.callback(
        Output(cid.STORE_UPLOAD_SELECTED_ROW, 'data', allow_duplicate=True),
        Output(cid.UPLOAD_SELECTION_LABEL, 'children', allow_duplicate=True),
        Output(cid.MODAL_UPLOAD, 'className', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'children', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'className', allow_duplicate=True),
        Output(cid.UPLOAD_SUMMARY_TABLE, 'selected_rows', allow_duplicate=True),
        Output(cid.STORE_ACTIVE_INPUT_SOURCE, 'data', allow_duplicate=True),
        *_LOAD_FORM_OUTPUTS_DUPLICATE,
        Input(cid.UPLOAD_SUMMARY_TABLE, 'selected_rows'),
        State(cid.UPLOAD_SUMMARY_TABLE, 'data'),
        State(cid.STORE_UPLOAD, 'data'),
        prevent_initial_call=True,
    )
    def on_upload_row_selected(
        selected_rows: list[int] | None,
        table_data: list[dict[str, str | int]] | None,
        upload_store: dict[str, object] | None,
    ) -> tuple[object, ...]:
        """Load a clicked upload row into the vessel form and close the modal."""
        form_no_updates = (no_update,) * len(FORM_COMPONENT_IDS)
        if not selected_rows or not table_data or upload_store is None:
            return (
                None,
                'Click a row to load it into the vessel form below.',
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                *form_no_updates,
            )

        row_index = selected_rows[0]
        if row_index < 0 or row_index >= len(table_data):
            return (
                None,
                'Click a row to load it into the vessel form below.',
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                *form_no_updates,
            )

        row = table_data[row_index]
        row_number = int(row['row_number'])
        vessel_name = str(row.get('vessel_name', ''))
        status = str(row.get('status', ''))

        if status == 'error':
            return (
                row_number,
                f'Row {row_number} ({vessel_name}) has errors and cannot be loaded.',
                MODAL_OPEN_CLASS,
                no_update,
                no_update,
                no_update,
                no_update,
                *form_no_updates,
            )

        raw = _raw_from_upload_store(upload_store, row_number)
        if raw is None:
            return (
                row_number,
                f'Row {row_number} ({vessel_name}) could not be read from the file.',
                MODAL_OPEN_CLASS,
                no_update,
                no_update,
                no_update,
                no_update,
                *form_no_updates,
            )

        form_tuple = _form_tuple_from_raw(session_factory, raw)
        if form_tuple is None:
            return (
                row_number,
                f'Row {row_number} ({vessel_name}) failed validation.',
                MODAL_OPEN_CLASS,
                'Validation failed for the selected row.',
                'validation-banner error',
                no_update,
                no_update,
                *form_no_updates,
            )

        if status == 'warning':
            banner_class = 'validation-banner warning'
        else:
            banner_class = 'validation-banner ok'
        if status == 'warning':
            banner_text = (
                f'Loaded row {row_number} ({vessel_name}) from file — review warnings, '
                'then Calculate valuation.'
            )
        else:
            banner_text = (
                f'Loaded row {row_number} ({vessel_name}) from file into the form. '
                'Click Calculate valuation when ready.'
            )
        return (
            row_number,
            f'Loaded row {row_number} ({vessel_name}) into the form.',
            MODAL_HIDDEN_CLASS,
            banner_text,
            banner_class,
            [],
            'file',
            *form_tuple,
        )

    @app.callback(
        Output(cid.STORE_COMPUTE, 'data', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'children', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'className', allow_duplicate=True),
        Output(cid.MODAL_DATABASE, 'className', allow_duplicate=True),
        Output(cid.STORE_ACTIVE_INPUT_SOURCE, 'data', allow_duplicate=True),
        *_LOAD_FORM_OUTPUTS_DUPLICATE,
        Input(cid.BTN_MODAL_DATABASE_LOAD, 'n_clicks'),
        State(cid.SELECT_SAVED_VESSEL, 'value'),
        prevent_initial_call=True,
    )
    def on_load_saved_vessel(
        n_clicks: int | None,
        vessel_input_id: int | None,
    ) -> tuple[object, ...]:
        """Load a saved silver row and its latest valuation into the UI."""
        if not n_clicks or vessel_input_id is None:
            return (no_update, no_update, no_update, no_update, no_update, *_FORM_NO_UPDATES)

        with session_scope(session_factory) as session:
            inputs = get_vessel_inputs(session, vessel_input_id)
            valuation = get_valuation(session, vessel_input_id)

        if inputs is None:
            return (
                no_update,
                'Saved vessel not found.',
                'validation-banner error',
                MODAL_OPEN_CLASS,
                no_update,
                *((no_update,) * len(FORM_COMPONENT_IDS)),
            )
        if valuation is None:
            return (
                no_update,
                'No valuation found for this vessel — run Calculate first.',
                'validation-banner error',
                MODAL_OPEN_CLASS,
                no_update,
                *((no_update,) * len(FORM_COMPONENT_IDS)),
            )

        schedules = scenario_schedules(inputs)
        store_data: dict[str, object] = {
            'inputs': vessel_inputs_to_store(inputs),
            'valuation': valuation_to_store(valuation),
            'schedules': schedules_to_store(schedules),
            'warnings': [],
            'vessel_input_id': vessel_input_id,
        }
        return (
            store_data,
            (
                f'Loaded entry #{vessel_input_id} ({inputs.vessel_name}) from the database. '
                'Available in Compare.'
            ),
            'validation-banner ok',
            MODAL_HIDDEN_CLASS,
            'database',
            *_form_values_tuple(inputs),
        )

    @app.callback(
        Output(cid.BTN_INPUT_OPTION_MANUAL, 'className'),
        Output(cid.INPUT_SOURCE_UPLOAD_WRAP, 'className'),
        Output(cid.BTN_INPUT_OPTION_DATABASE, 'className'),
        Input(cid.STORE_ACTIVE_INPUT_SOURCE, 'data'),
    )
    def highlight_input_source(active_source: str | None) -> tuple[str, str, str]:
        """Highlight the active vessel-input path in the top bar."""
        upload_class = 'input-source-upload'
        if active_source == 'file':
            upload_class = f'{upload_class} {INPUT_SOURCE_BTN_ACTIVE_CLASS}'
            return (
                INPUT_SOURCE_BTN_CLASS,
                upload_class,
                INPUT_SOURCE_BTN_CLASS,
            )
        if active_source == 'database':
            return (
                INPUT_SOURCE_BTN_CLASS,
                'input-source-upload',
                INPUT_SOURCE_BTN_ACTIVE_CLASS,
            )
        return (
            INPUT_SOURCE_BTN_ACTIVE_CLASS,
            'input-source-upload',
            INPUT_SOURCE_BTN_CLASS,
        )

    @app.callback(
        Output(cid.STORE_ACTIVE_INPUT_SOURCE, 'data'),
        Input(cid.BTN_INPUT_OPTION_MANUAL, 'n_clicks'),
        prevent_initial_call=True,
    )
    def select_manual_input_source(_n_clicks: int | None) -> str:
        """Mark manual entry as the active input path."""
        return 'manual'

    @app.callback(
        Output(cid.BANNER_VALIDATION, 'children', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'className', allow_duplicate=True),
        Output(cid.STORE_ACTIVE_INPUT_SOURCE, 'data', allow_duplicate=True),
        *_LOAD_FORM_OUTPUTS_DUPLICATE,
        Input(cid.BTN_RESET_BASECASE, 'n_clicks'),
        prevent_initial_call=True,
    )
    def reset_form_to_basecase(n_clicks: int | None) -> tuple[object, ...]:
        """Restore default base-case values on the vessel form."""
        if not n_clicks:
            return (no_update, no_update, no_update, *_FORM_NO_UPDATES)
        form_tuple = _default_form_values_tuple()
        return (
            'Form reset to base-case defaults.',
            'validation-banner ok',
            'manual',
            *form_tuple,
        )

    @app.callback(
        Output(cid.CONFIRM_DELETE_SAVED, 'displayed'),
        Input(cid.BTN_DELETE_SAVED, 'n_clicks'),
        State(cid.SELECT_SAVED_VESSELS_DELETE, 'value'),
        prevent_initial_call=True,
    )
    def show_delete_confirm(
        n_clicks: int | None,
        vessel_input_ids: list[int] | list[str] | int | float | str | None,
    ) -> bool:
        """Open confirm dialog when Delete is clicked and at least one entry is selected."""
        if not n_clicks:
            return False
        return bool(_normalize_vessel_input_ids(vessel_input_ids))

    @app.callback(
        Output(cid.CONFIRM_DELETE_SAVED, 'message'),
        Input(cid.SELECT_SAVED_VESSELS_DELETE, 'value'),
    )
    def delete_confirm_message(
        vessel_input_ids: list[int] | list[str] | int | float | str | None,
    ) -> str:
        """Confirm dialog text names the selected database ids."""
        normalized_ids = _normalize_vessel_input_ids(vessel_input_ids)
        if not normalized_ids:
            return 'Select one or more saved entries to delete.'
        id_list = ', '.join(f'#{vessel_input_id}' for vessel_input_id in normalized_ids)
        count = len(normalized_ids)
        noun = 'entry' if count == 1 else 'entries'
        return (
            f'Delete {count} saved {noun} ({id_list}) and their valuations from the database? '
            'This cannot be undone.'
        )

    @app.callback(
        Output(cid.STORE_COMPUTE, 'data', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'children', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'className', allow_duplicate=True),
        Output(cid.SELECT_SAVED_VESSEL, 'value'),
        Output(cid.SELECT_SAVED_VESSELS_DELETE, 'value'),
        Input(cid.CONFIRM_DELETE_SAVED, 'submit_n_clicks'),
        State(cid.SELECT_SAVED_VESSELS_DELETE, 'value'),
        State(cid.SELECT_SAVED_VESSEL, 'value'),
        State(cid.STORE_COMPUTE, 'data'),
        prevent_initial_call=True,
    )
    def on_delete_saved_vessel(
        submit_n_clicks: int | None,
        vessel_input_ids: list[int] | list[str] | int | float | str | None,
        loaded_vessel_input_id: int | None,
        compute_store: dict[str, object] | None,
    ) -> tuple[object, object, object, object, object]:
        """Delete all selected saved entries (not limited to the latest Calculate)."""
        if not submit_n_clicks:
            return no_update, no_update, no_update, no_update, no_update

        normalized_ids = _normalize_vessel_input_ids(vessel_input_ids)
        if not normalized_ids:
            return (
                no_update,
                'Select one or more saved entries to delete.',
                'validation-banner error',
                no_update,
                no_update,
            )

        with session_scope(session_factory) as session:
            deleted_count = delete_vessel_inputs(session, normalized_ids)

        if deleted_count == 0:
            id_list = ', '.join(f'#{vessel_input_id}' for vessel_input_id in normalized_ids)
            return (
                no_update,
                f'Saved {id_list} not found.',
                'validation-banner error',
                no_update,
                no_update,
            )

        cleared_store: object = no_update
        deleted_set = set(normalized_ids)
        if compute_store is not None:
            stored_id = compute_store.get('vessel_input_id')
            if isinstance(stored_id, int) and stored_id in deleted_set:
                cleared_store = None

        cleared_load: object = no_update
        if loaded_vessel_input_id is not None and loaded_vessel_input_id in deleted_set:
            cleared_load = None

        count = deleted_count
        noun = 'entry' if count == 1 else 'entries'
        return (
            cleared_store,
            f'Deleted {count} saved {noun} from the database.',
            'validation-banner ok',
            cleared_load,
            [],
        )

    @app.callback(
        Output(cid.SELECT_SAVED_VESSEL, 'options'),
        Output(cid.SELECT_SAVED_VESSELS_DELETE, 'options'),
        Output(cid.SELECT_COMPARE_A, 'options'),
        Output(cid.SELECT_COMPARE_B, 'options'),
        Output(cid.SELECT_CALCULATION_VESSEL, 'options'),
        Input(cid.BTN_CALCULATE, 'n_clicks'),
        Input(cid.BTN_SAVE_TO_DB, 'n_clicks'),
        Input(cid.BTN_MODAL_DATABASE_LOAD, 'n_clicks'),
        Input(cid.CONFIRM_DELETE_SAVED, 'submit_n_clicks'),
        prevent_initial_call=False,
    )
    def refresh_vessel_catalog(
        _calc_clicks: int | None,
        _save_clicks: int | None,
        _load_clicks: int | None,
        _delete_clicks: int | None,
    ) -> tuple[
        list[dict[str, str | int]],
        list[dict[str, str | int]],
        list[dict[str, str | int]],
        list[dict[str, str | int]],
        list[dict[str, str | int]],
    ]:
        """Populate saved-vessel dropdowns from the database."""
        with session_scope(session_factory) as session:
            options = _vessel_dropdown_options(session)
        return options, options, options, options, options

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
            return _EMPTY_COMPARE_FIGURE, compare_table_columns(), [], ''

        if vessel_a_id is None or vessel_b_id is None:
            return (
                _EMPTY_COMPARE_FIGURE,
                compare_table_columns(),
                [],
                'Select two saved vessels.',
            )
        if vessel_a_id == vessel_b_id:
            return (
                _EMPTY_COMPARE_FIGURE,
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
                _EMPTY_COMPARE_FIGURE,
                compare_table_columns(),
                [],
                'One or both saved vessels were not found.',
            )
        if valuation_a is None or valuation_b is None:
            return (
                _EMPTY_COMPARE_FIGURE,
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
        Output(cid.STORE_COMPUTE, 'data'),
        Output(cid.BANNER_VALIDATION, 'children'),
        Output(cid.BANNER_VALIDATION, 'className'),
        *_LOAD_FORM_OUTPUTS,
        Input(cid.BTN_CALCULATE, 'n_clicks'),
        State(cid.INPUT_REV_MIN, 'value'),
        State(cid.INPUT_REV_MAX, 'value'),
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
        *form_values: str | int | float | None,
    ) -> tuple[object, ...]:
        """Validate inputs, enrich in memory, and store results for both views."""
        if not n_clicks:
            return (no_update, no_update, no_update, *_FORM_NO_UPDATES)

        form = collect_form_values(*form_values)
        raw_payload = form_values_to_raw(form)

        rev_min_val = _optional_float(rev_min)
        rev_max_val = _optional_float(rev_max)

        with session_scope(session_factory) as session:
            fleet_peers = list_fleet_vessel_inputs(session)
            validation = validate(raw_payload)
            if validation.inputs is None:
                message = '; '.join(validation.errors) if validation.errors else 'Validation failed'
                return no_update, message, 'validation-banner error', *_FORM_NO_UPDATES

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
            result = enrich(inputs, rev_min=rev_min_val, rev_max=rev_max_val)

        warnings = list(validation.warnings)
        source = 'manual_form'
        schedules = scenario_schedules(inputs)
        store_data = _build_compute_store(
            inputs=inputs,
            result=result,
            schedules=schedules,
            warnings=warnings,
            raw_payload=raw_payload,
            source=source,
            rev_min=rev_min_val,
            rev_max=rev_max_val,
        )

        form_tuple = _form_values_tuple(inputs)
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

    @app.callback(
        Output(cid.STORE_COMPUTE, 'data', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'children', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'className', allow_duplicate=True),
        Input(cid.BTN_SAVE_TO_DB, 'n_clicks'),
        State(cid.STORE_COMPUTE, 'data'),
        prevent_initial_call=True,
    )
    def on_save_to_database(
        n_clicks: int | None,
        compute_store: dict[str, object] | None,
    ) -> tuple[object, object, object]:
        """Persist the last in-memory valuation to the database."""
        if not n_clicks:
            return no_update, no_update, no_update

        if compute_store is None or 'valuation' not in compute_store:
            return (
                no_update,
                'Calculate valuation first, then save to the database.',
                'validation-banner error',
            )

        stored_id = compute_store.get('vessel_input_id')
        if isinstance(stored_id, int):
            return (
                no_update,
                f'Already saved as entry #{stored_id}. Calculate again to save a new copy.',
                'validation-banner ok',
            )

        persist_context = compute_store.get('persist_context')
        if not isinstance(persist_context, dict):
            return (
                no_update,
                'Loaded entries are already saved. Calculate again to persist new inputs.',
                'validation-banner error',
            )

        raw_payload = persist_context.get('raw_payload')
        source = persist_context.get('source')
        if not isinstance(raw_payload, dict) or not isinstance(source, str):
            return (
                no_update,
                'Calculate valuation first, then save to the database.',
                'validation-banner error',
            )

        rev_min_raw = persist_context.get('rev_min')
        rev_max_raw = persist_context.get('rev_max')
        rev_min_val = _optional_float(rev_min_raw) if rev_min_raw is not None else None
        rev_max_val = _optional_float(rev_max_raw) if rev_max_raw is not None else None

        with session_scope(session_factory) as session:
            factor_benchmarks = load_pp_teu_factor_benchmarks(session)
            try:
                persisted = persist_vessel_submission(
                    session,
                    raw_payload,
                    source=source,
                    filename=None,
                    pp_teu_factor_benchmarks=factor_benchmarks,
                    rev_min=rev_min_val,
                    rev_max=rev_max_val,
                )
            except ValueError as exc:
                return no_update, str(exc), 'validation-banner error'

        inputs_raw = compute_store['inputs']
        assert isinstance(inputs_raw, dict)
        vessel_name = str(inputs_raw.get('vessel_name', 'vessel'))

        updated_store = dict(compute_store)
        updated_store['vessel_input_id'] = persisted.vessel_input_id
        updated_store.pop('persist_context', None)

        warnings_raw = compute_store.get('warnings')
        warnings = [str(w) for w in warnings_raw] if isinstance(warnings_raw, list) else []
        banner_class = 'validation-banner warning' if warnings else 'validation-banner ok'
        if warnings:
            banner_text = (
                f'Saved entry #{persisted.vessel_input_id} ({vessel_name}). '
                f'Warnings: {"; ".join(warnings)}'
            )
        else:
            banner_text = (
                f'Saved entry #{persisted.vessel_input_id} ({vessel_name}) to the database — '
                'available in Compare and Option 3 (Load from database).'
            )
        return updated_store, banner_text, banner_class

    @app.callback(
        Output(cid.EXEC_SUMMARY, 'children'),
        Output(cid.CARD_NPV, 'children'),
        Output(cid.CARD_IRR, 'children'),
        Output(cid.CARD_SIGNAL, 'children'),
        Output(cid.CARD_BREAKEVEN, 'children'),
        Output(cid.CARD_PAYBACK, 'children'),
        Output(cid.CHART_SENSITIVITY, 'figure'),
        Output(cid.TABLE_SCENARIOS, 'children'),
        Output(cid.META_READONLY, 'children'),
        Input(cid.STORE_COMPUTE, 'data'),
    )
    def render_investment_results(
        store: dict[str, object] | None,
    ) -> tuple[object, object, object, object, object, object, object, object, object]:
        """Render View 1 outputs from the compute store."""
        empty = '—'
        empty_summary = html.P(
            'Run Calculate valuation or load from the database to see the executive summary.',
            className='help-text',
        )
        empty_figure: dict[str, object] = {
            'data': [],
            'layout': {'title': 'Run a valuation to see sensitivity'},
        }
        if store is None or 'valuation' not in store:
            return (
                empty_summary,
                empty,
                empty,
                empty,
                empty,
                empty,
                empty_figure,
                html.Div(),
                html.Div(),
            )

        valuation = store['valuation']
        assert isinstance(valuation, dict)
        npv = _float_field(valuation, 'npv')
        irr_raw = valuation['irr']
        irr = _float_field(valuation, 'irr') if irr_raw is not None else None
        signal = str(valuation['investment_signal'])
        breakeven_raw = valuation['breakeven_rate']
        breakeven = _float_field(valuation, 'breakeven_rate') if breakeven_raw is not None else None
        payback_raw = valuation.get('payback_year')
        payback: int | None = None
        if isinstance(payback_raw, int):
            payback = payback_raw
        elif isinstance(payback_raw, float):
            payback = int(payback_raw)

        sensitivity = valuation['sensitivity']
        assert isinstance(sensitivity, list)
        figure = _sensitivity_figure(sensitivity)

        scenarios = valuation['scenarios']
        assert isinstance(scenarios, dict)
        scenario_table = scenario_summary_table(scenarios)

        inputs_raw = store['inputs']
        assert isinstance(inputs_raw, dict)
        inputs = vessel_inputs_from_store(inputs_raw)
        meta = format_metadata(inputs)

        warnings_raw = store.get('warnings')
        warnings = [str(w) for w in warnings_raw] if isinstance(warnings_raw, list) else []
        stored_id_raw = store.get('vessel_input_id')
        vessel_input_id = stored_id_raw if isinstance(stored_id_raw, int) else None

        summary = executive_summary_panel(
            inputs.vessel_name,
            vessel_input_id,
            valuation,
            warnings,
            inputs.discount_rate,
        )
        signal_css = _signal_css_class(signal)

        return (
            summary,
            format_npv(npv),
            format_irr(irr),
            html.Span(format_signal_label(signal), className=signal_css),
            format_rate_per_day(breakeven),
            format_payback_year(payback),
            figure,
            scenario_table,
            meta,
        )

    @app.callback(
        Output(cid.TABLE_CASHFLOW, 'data'),
        Output(cid.CALCULATION_PLACEHOLDER, 'children'),
        Input(cid.SELECT_SCENARIO, 'value'),
        Input(cid.STORE_COMPUTE, 'data'),
        Input(cid.SELECT_CALCULATION_VESSEL, 'value'),
    )
    def render_cashflow_table(
        scenario: str | None,
        store: dict[str, object] | None,
        calculation_vessel_id: int | None,
    ) -> tuple[list[dict[str, str | int]], str]:
        """Render cashflow rows from the session store or a selected database entry."""
        if scenario is None:
            return [], 'Select a scenario to view the schedule.'

        schedules, placeholder = _calculation_schedules(
            session_factory,
            store,
            calculation_vessel_id,
        )
        if schedules is None:
            return [], placeholder

        schedule = schedules.get(scenario, [])
        return schedule_to_rows(schedule), placeholder


def _calculation_schedules(
    session_factory: sessionmaker[Session],
    compute_store: dict[str, object] | None,
    calculation_vessel_id: int | None,
) -> tuple[dict[str, list[CashflowYear]] | None, str]:
    """Resolve scenario schedules from an explicit DB pick or the active session."""
    if calculation_vessel_id is not None:
        with session_scope(session_factory) as session:
            inputs = get_vessel_inputs(session, calculation_vessel_id)
        if inputs is None:
            return None, f'Saved entry #{calculation_vessel_id} was not found in the database.'
        schedules = scenario_schedules(inputs)
        return schedules, (
            f'Showing entry #{calculation_vessel_id} ({inputs.vessel_name}) from the database.'
        )

    if compute_store is not None and 'schedules' in compute_store:
        schedules_raw = compute_store['schedules']
        if isinstance(schedules_raw, dict):
            schedules = schedules_from_store(schedules_raw)  # type: ignore[arg-type]
            vessel_input_id = compute_store.get('vessel_input_id')
            if isinstance(vessel_input_id, int):
                return schedules, (
                    f'Using active session from entry #{vessel_input_id} '
                    '(Calculate or Load on Investment tab).'
                )
            return schedules, 'Using active session from the Investment tab.'

    return (
        None,
        'Run Calculate on the Investment tab, or select a saved entry above.',
    )


def _form_values_tuple(inputs: VesselInputs) -> tuple[str | int | float | None, ...]:
    """Form field values in ``FORM_FIELD_NAMES`` order for Dash ``Output`` wiring."""
    form_values = vessel_inputs_to_form_values(inputs)
    return tuple(form_values[name] for name in FORM_FIELD_NAMES)


def _build_compute_store(
    *,
    inputs: VesselInputs,
    result: ValuationResult,
    schedules: dict[str, list[CashflowYear]],
    warnings: list[str],
    raw_payload: dict[str, object],
    source: str,
    rev_min: float | None,
    rev_max: float | None,
    vessel_input_id: int | None = None,
) -> dict[str, object]:
    """Serialize an in-memory valuation for the compute store."""
    store_data: dict[str, object] = {
        'inputs': vessel_inputs_to_store(inputs),
        'valuation': valuation_to_store(result),
        'schedules': schedules_to_store(schedules),
        'warnings': warnings,
        'vessel_input_id': vessel_input_id,
    }
    if vessel_input_id is None:
        store_data['persist_context'] = {
            'raw_payload': raw_payload,
            'source': source,
            'rev_min': rev_min,
            'rev_max': rev_max,
        }
    return store_data


def _format_upload_preview_cell(value: object) -> str:
    """Format a parsed spreadsheet cell for the upload preview table."""
    if value is None:
        return ''
    if isinstance(value, float):
        if value.is_integer():
            return f'{int(value):,}'
        return f'{value:,.2f}'
    if isinstance(value, int):
        return f'{value:,}'
    return str(value).strip()


def _upload_preview_row(row_number: int, raw: dict[str, object]) -> dict[str, str | int]:
    """Build one preview-table row from parsed file values."""
    return {
        'row_number': row_number,
        'vessel_name': _format_upload_preview_cell(raw.get('vessel_name')),
        'teu_size': _format_upload_preview_cell(raw.get('teu_size')),
        'purchase_price': _format_upload_preview_cell(raw.get('purchase_price')),
    }


def _raw_from_upload_store(
    upload_store: dict[str, object],
    row_number: int,
) -> dict[str, object] | None:
    """Look up parsed row payload from the upload store."""
    rows = upload_store.get('rows')
    if not isinstance(rows, list):
        return None
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        if entry.get('row_number') == row_number and not entry.get('errors'):
            raw = entry.get('raw')
            if isinstance(raw, dict):
                return raw
    return None


def _form_tuple_from_raw(
    session_factory: sessionmaker[Session],
    raw: dict[str, object],
) -> tuple[str | int | float | None, ...] | None:
    """Validate a raw payload and return Dash form values."""
    with session_scope(session_factory) as session:
        fleet_peers = list_fleet_vessel_inputs(session)
    validation = validate(raw)
    if validation.inputs is None:
        return None
    factor_benchmarks = pp_teu_factor_benchmarks_for_subject(fleet_peers, validation.inputs)
    if factor_benchmarks:
        validation = validate(raw, pp_teu_factor_benchmarks=factor_benchmarks)
    if validation.inputs is None:
        return None
    return _form_values_tuple(validation.inputs)


def _default_form_values_tuple() -> tuple[str | int | float | None, ...]:
    """Default vessel-form values for reset-to-base-case."""
    return tuple(
        format_form_field_value(field_name, FORM_DEFAULTS[field_name])
        for field_name in FORM_FIELD_NAMES
    )


def _optional_float(value: float | str | int | None) -> float | None:
    if value is None or value == '':
        return None
    return float(value)


def _sensitivity_figure(sensitivity: list[dict[str, object]]) -> dict[str, object]:
    revenues: list[float] = []
    irrs: list[float] = []
    for point in sensitivity:
        if not isinstance(point, dict):
            continue
        try:
            rev = _float_field(point, 'revenue_per_day')
        except (KeyError, TypeError):
            continue
        irr_val = point.get('irr')
        irr_pct = _float_field(point, 'irr') * 100 if irr_val is not None else float('nan')
        revenues.append(rev)
        irrs.append(irr_pct)

    fig = go.Figure(
        data=[
            go.Scatter(
                x=revenues,
                y=irrs,
                mode='lines+markers',
                name='IRR',
            )
        ]
    )
    fig.update_layout(
        title='IRR vs revenue per day',
        xaxis_title='Revenue per day ($)',
        yaxis_title='IRR (%)',
        template='plotly_white',
    )
    return fig.to_dict()


def _signal_css_class(signal: str) -> str:
    """Map investment signal to a presentation CSS class."""
    return {
        'INVEST': 'signal-invest',
        'MARGINAL': 'signal-marginal',
        'DO NOT INVEST': 'signal-reject',
    }.get(signal, '')


def _vessel_dropdown_options(session: Session) -> list[dict[str, str | int]]:
    """Build dropdown options for saved silver vessel rows (id disambiguates duplicates)."""
    vessels = list_vessels(session)
    return [
        {
            'label': format_saved_vessel_option_label(summary),
            'value': summary.id,
        }
        for summary in vessels
    ]
