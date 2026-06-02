"""Shared helpers for Dash callback wiring."""

from typing import TYPE_CHECKING
from typing import cast

import plotly.graph_objects as go
from dash import Output
from dash import no_update

from app.form_defaults import DEFAULT_SIGNAL_BAND
from app.form_defaults import FORM_DEFAULTS
from app.form_formatting import format_form_field_value
from app.serialization import schedules_from_store
from app.serialization import schedules_to_store
from app.serialization import valuation_to_store
from app.serialization import vessel_inputs_to_form_values
from app.serialization import vessel_inputs_to_store
from app.views.investment import FORM_COMPONENT_IDS
from app.views.investment import FORM_FIELD_NAMES
from app.views.investment import format_saved_vessel_option_label
from vessel_valuation.db.connection import session_scope
from vessel_valuation.db.repository import get_vessel_inputs
from vessel_valuation.db.repository import list_fleet_vessel_inputs
from vessel_valuation.db.repository import list_vessels
from vessel_valuation.decision_insights.scenario_schedules import scenario_schedules
from vessel_valuation.file_parser import pp_teu_factor_benchmarks_for_subject
from vessel_valuation.mapping import VesselInputField
from vessel_valuation.schema import SIGNAL_BAND
from vessel_valuation.serialize import json_float
from vessel_valuation.serialize import scenario_bundles_from_json
from vessel_valuation.serialize import scenario_bundles_to_json
from vessel_valuation.validation import validate

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from sqlalchemy.orm import sessionmaker

    from vessel_valuation.schema import CashflowYear
    from vessel_valuation.schema import ScenarioBundle
    from vessel_valuation.schema import ValuationResult
    from vessel_valuation.schema import VesselInputs

LOAD_FORM_OUTPUTS = [Output(component_id, 'value') for component_id in FORM_COMPONENT_IDS]
LOAD_FORM_OUTPUTS_DUPLICATE = [
    Output(component_id, 'value', allow_duplicate=True) for component_id in FORM_COMPONENT_IDS
]
FORM_NO_UPDATES = (no_update,) * len(FORM_COMPONENT_IDS)

EMPTY_COMPARE_FIGURE: dict[str, object] = {
    'data': [],
    'layout': {'title': 'Select vessels and line item, then click Compare'},
}


def normalize_vessel_input_ids(
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


def calculation_schedules(
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
            schedules = schedules_from_store(
                cast('dict[str, list[dict[str, object]]]', schedules_raw),
            )
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


def form_values_tuple(inputs: VesselInputs) -> tuple[str | int | float | None, ...]:
    """Form field values in ``FORM_FIELD_NAMES`` order for Dash ``Output`` wiring."""
    form_values = vessel_inputs_to_form_values(inputs)
    return tuple(form_values[VesselInputField(name)] for name in FORM_FIELD_NAMES)


def _scenario_bundles_from_compute_store(
    compute_store: dict[str, object] | None,
) -> list[ScenarioBundle] | None:
    if compute_store is None:
        return None
    bundles_raw = compute_store.get('scenario_bundles')
    if not isinstance(bundles_raw, list):
        return None
    return scenario_bundles_from_json(cast('list[dict[str, object]]', bundles_raw))


def build_compute_store(
    *,
    inputs: VesselInputs,
    result: ValuationResult,
    schedules: dict[str, list[CashflowYear]],
    scenario_bundles: list[ScenarioBundle],
    warnings: list[str],
    raw_payload: dict[str, object],
    source: str,
    rev_min: float | None,
    rev_max: float | None,
    signal_band: float,
    vessel_input_id: int | None = None,
) -> dict[str, object]:
    """Serialize an in-memory valuation for the compute store."""
    store_data: dict[str, object] = {
        'inputs': vessel_inputs_to_store(inputs),
        'valuation': valuation_to_store(result),
        'schedules': schedules_to_store(schedules),
        'scenario_bundles': scenario_bundles_to_json(scenario_bundles),
        'warnings': warnings,
        'vessel_input_id': vessel_input_id,
    }
    if vessel_input_id is None:
        store_data['persist_context'] = {
            'raw_payload': raw_payload,
            'source': source,
            'rev_min': rev_min,
            'rev_max': rev_max,
            'signal_band': signal_band,
            'scenario_bundles': scenario_bundles_to_json(scenario_bundles),
        }
    return store_data


def format_upload_preview_cell(value: object) -> str:
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


def upload_preview_row(row_number: int, raw: dict[str, object]) -> dict[str, str | int]:
    """Build one preview-table row from parsed file values."""
    return {
        'row_number': row_number,
        'vessel_name': format_upload_preview_cell(raw.get('vessel_name')),
        'teu_size': format_upload_preview_cell(raw.get('teu_size')),
        'purchase_price': format_upload_preview_cell(raw.get('purchase_price')),
    }


def raw_from_upload_store(
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
        row = cast('dict[str, object]', entry)
        if row.get('row_number') == row_number and not row.get('errors'):
            raw = row.get('raw')
            if isinstance(raw, dict):
                return cast('dict[str, object]', raw)
    return None


def form_tuple_from_raw(
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
    return form_values_tuple(validation.inputs)


def default_form_values_tuple() -> tuple[str | int | float | None, ...]:
    """Default vessel-form values for reset-to-base-case."""
    return tuple(
        format_form_field_value(field_name, FORM_DEFAULTS[field_name])
        for field_name in FORM_FIELD_NAMES
    )


def optional_float(value: float | str | int | None) -> float | None:
    if value is None or value == '':
        return None
    return float(value)


def parse_signal_band(value: float | str | int | None) -> float:
    """Coerce settings input to a valid investment-signal band (decimal)."""
    if value is None or value == '':
        return SIGNAL_BAND
    try:
        band = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            'Investment signal band must be a number (e.g. 0.02 for 2 percentage points).'
        ) from exc
    if band <= 0 or band >= 1:
        raise ValueError('Investment signal band must be greater than 0 and less than 1.')
    return band


def default_signal_band_value() -> float:
    """Default signal-band setting for reset and initial layout."""
    return DEFAULT_SIGNAL_BAND


def sensitivity_figure(sensitivity: list[dict[str, object]]) -> dict[str, object]:
    revenues: list[float] = []
    irrs: list[float] = []
    for point in sensitivity:
        if not isinstance(point, dict):
            continue
        try:
            rev = json_float(point['revenue_per_day'], 'revenue_per_day')
        except (KeyError, TypeError):
            continue
        irr_val = point.get('irr')
        irr_pct = json_float(point['irr'], 'irr') * 100 if irr_val is not None else float('nan')
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


def signal_css_class(signal: str) -> str:
    """Map investment signal to a presentation CSS class."""
    return {
        'FAVORABLE': 'signal-invest',
        'MARGINAL': 'signal-marginal',
        'UNFAVORABLE': 'signal-reject',
        # Legacy values from saved rows before signal rename
        'INVEST': 'signal-invest',
        'DO NOT INVEST': 'signal-reject',
    }.get(signal, '')


def vessel_dropdown_options(session: Session) -> list[dict[str, str | int]]:
    """Build dropdown options for saved silver vessel rows (id disambiguates duplicates)."""
    vessels = list_vessels(session)
    return [
        {
            'label': format_saved_vessel_option_label(summary),
            'value': summary.id,
        }
        for summary in vessels
    ]
