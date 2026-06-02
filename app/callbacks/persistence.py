"""Save, load, and delete saved vessel callbacks."""

from typing import TYPE_CHECKING
from typing import cast

from dash import Dash
from dash import no_update
from dash.dependencies import Input
from dash.dependencies import Output
from dash.dependencies import State

from app import component_ids as cid
from app.callbacks._helpers import FORM_COMPONENT_IDS
from app.callbacks._helpers import FORM_NO_UPDATES
from app.callbacks._helpers import LOAD_FORM_OUTPUTS_DUPLICATE
from app.callbacks._helpers import default_form_values_tuple
from app.callbacks._helpers import form_values_tuple
from app.callbacks._helpers import normalize_vessel_input_ids
from app.callbacks._helpers import optional_float
from app.serialization import schedules_to_store
from app.serialization import valuation_to_store
from app.serialization import vessel_inputs_to_store
from app.views.investment import MODAL_HIDDEN_CLASS
from app.views.investment import MODAL_OPEN_CLASS
from vessel_valuation.db.connection import session_scope
from vessel_valuation.db.repository import delete_vessel_inputs
from vessel_valuation.db.repository import get_valuation
from vessel_valuation.db.repository import get_vessel_inputs
from vessel_valuation.db.repository import load_pp_teu_factor_benchmarks
from vessel_valuation.db.repository import persist_vessel_submission
from vessel_valuation.decision_insights.scenario_analysis import DEFAULT_SCENARIO_BUNDLES
from vessel_valuation.decision_insights.scenario_schedules import scenario_schedules
from vessel_valuation.serialize import scenario_bundles_from_json
from vessel_valuation.serialize import scenario_bundles_to_json

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from sqlalchemy.orm import sessionmaker


def register(app: Dash, session_factory: sessionmaker[Session]) -> None:
    """Register database persistence and picker-modal callbacks."""

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
        Output(cid.STORE_COMPUTE, 'data', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'children', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'className', allow_duplicate=True),
        Output(cid.MODAL_DATABASE, 'className', allow_duplicate=True),
        Output(cid.STORE_ACTIVE_INPUT_SOURCE, 'data', allow_duplicate=True),
        *LOAD_FORM_OUTPUTS_DUPLICATE,
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
            return (no_update, no_update, no_update, no_update, no_update, *FORM_NO_UPDATES)

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

        default_bundles = list(DEFAULT_SCENARIO_BUNDLES)
        schedules = scenario_schedules(inputs, bundles=default_bundles)
        store_data: dict[str, object] = {
            'inputs': vessel_inputs_to_store(inputs),
            'valuation': valuation_to_store(valuation),
            'schedules': schedules_to_store(schedules),
            'scenario_bundles': scenario_bundles_to_json(default_bundles),
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
            *form_values_tuple(inputs),
        )

    @app.callback(
        Output(cid.BANNER_VALIDATION, 'children', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'className', allow_duplicate=True),
        Output(cid.STORE_ACTIVE_INPUT_SOURCE, 'data', allow_duplicate=True),
        *LOAD_FORM_OUTPUTS_DUPLICATE,
        Input(cid.BTN_RESET_BASECASE, 'n_clicks'),
        prevent_initial_call=True,
    )
    def reset_form_to_basecase(n_clicks: int | None) -> tuple[object, ...]:
        """Restore default base-case values on the vessel form."""
        if not n_clicks:
            return (no_update, no_update, no_update, *FORM_NO_UPDATES)
        form_tuple = default_form_values_tuple()
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
        return bool(normalize_vessel_input_ids(vessel_input_ids))

    @app.callback(
        Output(cid.CONFIRM_DELETE_SAVED, 'message'),
        Input(cid.SELECT_SAVED_VESSELS_DELETE, 'value'),
    )
    def delete_confirm_message(
        vessel_input_ids: list[int] | list[str] | int | float | str | None,
    ) -> str:
        """Confirm dialog text names the selected database ids."""
        normalized_ids = normalize_vessel_input_ids(vessel_input_ids)
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

        normalized_ids = normalize_vessel_input_ids(vessel_input_ids)
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

        persist_context_raw = compute_store.get('persist_context')
        if not isinstance(persist_context_raw, dict):
            return (
                no_update,
                'Loaded entries are already saved. Calculate again to persist new inputs.',
                'validation-banner error',
            )
        persist_context = cast('dict[str, object]', persist_context_raw)

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
        rev_min_val = (
            optional_float(cast('int | float | str', rev_min_raw)) if rev_min_raw is not None else None
        )
        rev_max_val = (
            optional_float(cast('int | float | str', rev_max_raw)) if rev_max_raw is not None else None
        )

        bundles_raw = persist_context.get('scenario_bundles')
        scenario_bundles = (
            scenario_bundles_from_json(cast('list[dict[str, object]]', bundles_raw))
            if isinstance(bundles_raw, list)
            else None
        )

        with session_scope(session_factory) as session:
            factor_benchmarks = load_pp_teu_factor_benchmarks(session)
            try:
                persisted = persist_vessel_submission(
                    session,
                    cast('dict[str, object]', raw_payload),
                    source=source,
                    filename=None,
                    pp_teu_factor_benchmarks=factor_benchmarks,
                    rev_min=rev_min_val,
                    rev_max=rev_max_val,
                    scenario_bundles=scenario_bundles,
                )
            except ValueError as exc:
                return no_update, str(exc), 'validation-banner error'

        inputs_raw = compute_store['inputs']
        assert isinstance(inputs_raw, dict)
        inputs = cast('dict[str, object]', inputs_raw)
        vessel_name = str(inputs.get('vessel_name', 'vessel'))

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
