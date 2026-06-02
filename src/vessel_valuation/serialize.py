"""JSON-safe dict conversions for valuation result types.

Wire format is shared by SQLAlchemy JSON columns on ``VesselValuationRow`` and
``dcc.Store`` payloads in ``app.serialization``. Domain shapes live in ``schema.py``.

Callers
-------
``sensitivity_points_to_json`` / ``sensitivity_points_from_json``
    ``db.repository.save_valuation``, ``_valuation_row_to_result``; store valuation dict.
``scenarios_to_json`` / ``scenarios_from_json``
    Same paths for Best / Base / Worst summaries.
``cashflow_year_to_json`` / ``cashflow_year_from_json``
    Per-scenario schedule blobs in the browser store (DB schedule uses ORM rows).
``valuation_summary_to_json``
    Full valuation summary dict for ``dcc.Store`` (scalars plus nested JSON fields).
"""

import dataclasses
from datetime import date

from vessel_valuation.schema import (
    CashflowYear,
    ScenarioResult,
    SensitivityPoint,
    ValuationResult,
)

_CASHFLOW_YEAR_FIELDS = dataclasses.fields(CashflowYear)


def json_float(value: object, key: str = 'value') -> float:
    """Coerce a JSON round-tripped value to ``float``."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError(f'{key} must be numeric')


def json_int(value: object, key: str = 'value') -> int:
    """Coerce a JSON round-tripped value to ``int`` (reject bool)."""
    if isinstance(value, bool):
        raise TypeError(f'{key} must be an integer')
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise TypeError(f'{key} must be an integer')


def _optional_json_float(value: object) -> float | None:
    if value is None:
        return None
    return json_float(value)


def sensitivity_point_to_json(point: SensitivityPoint) -> dict[str, object]:
    """Serialize one sensitivity curve point."""
    return {'revenue_per_day': point.revenue_per_day, 'irr': point.irr}


def sensitivity_points_to_json(points: list[SensitivityPoint]) -> list[dict[str, object]]:
    """Serialize the IRR-vs-revenue sensitivity list for JSON storage."""
    return [sensitivity_point_to_json(point) for point in points]


def sensitivity_points_from_json(
    payload: list[dict[str, object]] | None,
) -> list[SensitivityPoint]:
    """Deserialize sensitivity points from a JSON column or store payload."""
    if not payload:
        return []
    result: list[SensitivityPoint] = []
    for point in payload:
        irr_raw = point.get('irr')
        irr = _optional_json_float(irr_raw) if irr_raw is not None else None
        result.append(
            SensitivityPoint(
                revenue_per_day=json_float(point['revenue_per_day'], 'revenue_per_day'),
                irr=irr,
            )
        )
    return result


def scenario_result_to_json(scenario: ScenarioResult) -> dict[str, object]:
    """Serialize one Best / Base / Worst scenario summary."""
    return {
        'npv': scenario.npv,
        'irr': scenario.irr,
        'investment_signal': scenario.investment_signal,
    }


def scenarios_to_json(
    scenarios: dict[str, ScenarioResult],
) -> dict[str, dict[str, object]]:
    """Serialize scenario summaries keyed by bundle name."""
    return {name: scenario_result_to_json(scenario) for name, scenario in scenarios.items()}


def scenario_result_from_json(data: dict[str, object]) -> ScenarioResult:
    """Deserialize one scenario summary."""
    irr_raw = data.get('irr')
    irr = _optional_json_float(irr_raw) if irr_raw is not None else None
    return ScenarioResult(
        npv=json_float(data['npv'], 'npv'),
        irr=irr,
        investment_signal=str(data['investment_signal']),
    )


def scenarios_from_json(
    payload: dict[str, dict[str, object]] | None,
) -> dict[str, ScenarioResult]:
    """Deserialize scenario summaries from a JSON column or store payload."""
    if not payload:
        return {}
    return {name: scenario_result_from_json(data) for name, data in payload.items()}


def cashflow_year_to_json(row: CashflowYear) -> dict[str, object]:
    """Serialize one schedule year for JSON storage (``period_end`` as ISO date)."""
    data = {field.name: getattr(row, field.name) for field in _CASHFLOW_YEAR_FIELDS}
    data['period_end'] = row.period_end.isoformat()
    return data


def cashflow_year_from_json(data: dict[str, object]) -> CashflowYear:
    """Deserialize one schedule year from a store payload."""
    period_end_raw = data['period_end']
    if not isinstance(period_end_raw, str):
        raise TypeError('period_end must be an ISO date string')
    return CashflowYear(
        year=json_int(data['year'], 'year'),
        period_end=date.fromisoformat(period_end_raw),
        revenue=json_float(data['revenue'], 'revenue'),
        opex=json_float(data['opex'], 'opex'),
        drydock_capex=json_float(data['drydock_capex'], 'drydock_capex'),
        upgrades_capex=json_float(data['upgrades_capex'], 'upgrades_capex'),
        free_cashflow=json_float(data['free_cashflow'], 'free_cashflow'),
        net_cashflow=json_float(data['net_cashflow'], 'net_cashflow'),
        discounted_cashflow=json_float(data['discounted_cashflow'], 'discounted_cashflow'),
        cumulative_cashflow=json_float(data['cumulative_cashflow'], 'cumulative_cashflow'),
    )


def valuation_summary_to_json(result: ValuationResult) -> dict[str, object]:
    """Serialize valuation summary fields for ``dcc.Store`` (excludes schedule rows)."""
    return {
        'npv': result.npv,
        'irr': result.irr,
        'payback_year': result.payback_year,
        'investment_signal': result.investment_signal,
        'breakeven_rate': result.breakeven_rate,
        'sensitivity': sensitivity_points_to_json(result.sensitivity),
        'scenarios': scenarios_to_json(result.scenarios),
    }
