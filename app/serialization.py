"""Serialize domain objects for ``dcc.Store`` (JSON-safe dicts)."""

from app.form_formatting import (
    COMMA_FORMATTED_FIELDS,
    format_form_values_for_display,
    parse_display_number,
)
from vessel_valuation.mapping import (
    vessel_inputs_from_dict,
    vessel_inputs_to_dict,
    vessel_inputs_to_form_raw_dict,
)
from vessel_valuation.schema import (
    CashflowYear,
    ScenarioResult,
    SensitivityPoint,
    ValuationResult,
    VesselInputs,
)
from vessel_valuation.serialize import (
    cashflow_year_from_json,
    cashflow_year_to_json,
    scenario_result_from_json,
    sensitivity_points_from_json,
    valuation_summary_to_json,
)


def form_values_to_raw(form: dict[str, str | int | float | None]) -> dict[str, object]:
    """Map Dash form state to a raw payload for ``validate()``."""
    raw: dict[str, object] = {}
    for key, value in form.items():
        if value is None or value == '':
            raw[key] = None
            continue
        if key in COMMA_FORMATTED_FIELDS:
            parsed = parse_display_number(value)
            raw[key] = parsed
            continue
        raw[key] = value
    return raw


def vessel_inputs_to_form_values(inputs: VesselInputs) -> dict[str, str | int | float | None]:
    """Map ``VesselInputs`` to Dash form component values (comma-formatted where configured)."""
    return format_form_values_for_display(vessel_inputs_to_form_raw_dict(inputs))


def vessel_inputs_to_store(inputs: VesselInputs) -> dict[str, object]:
    """Serialize ``VesselInputs`` for ``dcc.Store``."""
    return vessel_inputs_to_dict(inputs)


def vessel_inputs_from_store(data: dict[str, object]) -> VesselInputs:
    """Deserialize ``VesselInputs`` from ``dcc.Store``."""
    return vessel_inputs_from_dict(data)


def valuation_to_store(result: ValuationResult) -> dict[str, object]:
    """Serialize ``ValuationResult`` summary fields for ``dcc.Store``."""
    return valuation_summary_to_json(result)


def schedules_to_store(
    schedules: dict[str, list[CashflowYear]],
) -> dict[str, list[dict[str, object]]]:
    """Serialize per-scenario schedules for ``dcc.Store``."""
    return {name: [cashflow_year_to_json(row) for row in rows] for name, rows in schedules.items()}


def schedules_from_store(
    data: dict[str, list[dict[str, object]]],
) -> dict[str, list[CashflowYear]]:
    """Deserialize per-scenario schedules from ``dcc.Store``."""
    return {name: [cashflow_year_from_json(row) for row in rows] for name, rows in data.items()}


def cashflow_year_to_store(row: CashflowYear) -> dict[str, object]:
    """Serialize one ``CashflowYear`` for ``dcc.Store``."""
    return cashflow_year_to_json(row)


def cashflow_year_from_store(data: dict[str, object]) -> CashflowYear:
    """Deserialize one ``CashflowYear`` from ``dcc.Store``."""
    return cashflow_year_from_json(data)


def scenario_result_from_store(data: dict[str, object]) -> ScenarioResult:
    """Deserialize one ``ScenarioResult`` summary from ``dcc.Store``."""
    return scenario_result_from_json(data)


def sensitivity_from_store(
    points: list[dict[str, object]],
) -> list[SensitivityPoint]:
    """Deserialize sensitivity points from ``dcc.Store``."""
    return sensitivity_points_from_json(points)
