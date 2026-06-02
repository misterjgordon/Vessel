"""Serialize domain objects for ``dcc.Store`` (JSON-safe dicts)."""

from datetime import date

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


def _float_field(data: dict[str, object], key: str) -> float:
    value = data[key]
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError(f'{key} must be numeric')


def _int_field(data: dict[str, object], key: str) -> int:
    value = data[key]
    if isinstance(value, bool):
        raise TypeError(f'{key} must be an integer')
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise TypeError(f'{key} must be an integer')


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
    return {
        'npv': result.npv,
        'irr': result.irr,
        'payback_year': result.payback_year,
        'investment_signal': result.investment_signal,
        'breakeven_rate': result.breakeven_rate,
        'sensitivity': [
            {'revenue_per_day': p.revenue_per_day, 'irr': p.irr} for p in result.sensitivity
        ],
        'scenarios': {
            name: {
                'npv': s.npv,
                'irr': s.irr,
                'investment_signal': s.investment_signal,
            }
            for name, s in result.scenarios.items()
        },
    }


def schedules_to_store(
    schedules: dict[str, list[CashflowYear]],
) -> dict[str, list[dict[str, object]]]:
    """Serialize per-scenario schedules for ``dcc.Store``."""
    return {name: [cashflow_year_to_store(row) for row in rows] for name, rows in schedules.items()}


def schedules_from_store(
    data: dict[str, list[dict[str, object]]],
) -> dict[str, list[CashflowYear]]:
    """Deserialize per-scenario schedules from ``dcc.Store``."""
    return {name: [cashflow_year_from_store(row) for row in rows] for name, rows in data.items()}


def cashflow_year_to_store(row: CashflowYear) -> dict[str, object]:
    """Serialize one ``CashflowYear``."""
    return {
        'year': row.year,
        'period_end': row.period_end.isoformat(),
        'revenue': row.revenue,
        'opex': row.opex,
        'drydock_capex': row.drydock_capex,
        'upgrades_capex': row.upgrades_capex,
        'free_cashflow': row.free_cashflow,
        'net_cashflow': row.net_cashflow,
        'discounted_cashflow': row.discounted_cashflow,
        'cumulative_cashflow': row.cumulative_cashflow,
    }


def cashflow_year_from_store(data: dict[str, object]) -> CashflowYear:
    """Deserialize one ``CashflowYear``."""
    period_end_raw = data['period_end']
    if not isinstance(period_end_raw, str):
        raise TypeError('period_end must be an ISO date string')
    return CashflowYear(
        year=_int_field(data, 'year'),
        period_end=date.fromisoformat(period_end_raw),
        revenue=_float_field(data, 'revenue'),
        opex=_float_field(data, 'opex'),
        drydock_capex=_float_field(data, 'drydock_capex'),
        upgrades_capex=_float_field(data, 'upgrades_capex'),
        free_cashflow=_float_field(data, 'free_cashflow'),
        net_cashflow=_float_field(data, 'net_cashflow'),
        discounted_cashflow=_float_field(data, 'discounted_cashflow'),
        cumulative_cashflow=_float_field(data, 'cumulative_cashflow'),
    )


def scenario_result_from_store(data: dict[str, object]) -> ScenarioResult:
    """Deserialize one ``ScenarioResult`` summary."""
    irr_value = data['irr']
    irr = _float_field({'irr': irr_value}, 'irr') if irr_value is not None else None
    return ScenarioResult(
        npv=_float_field(data, 'npv'),
        irr=irr,
        investment_signal=str(data['investment_signal']),
    )


def sensitivity_from_store(
    points: list[dict[str, object]],
) -> list[SensitivityPoint]:
    """Deserialize sensitivity points."""
    result: list[SensitivityPoint] = []
    for p in points:
        irr_raw = p['irr']
        irr = _float_field(p, 'irr') if irr_raw is not None else None
        result.append(
            SensitivityPoint(
                revenue_per_day=_float_field(p, 'revenue_per_day'),
                irr=irr,
            )
        )
    return result
