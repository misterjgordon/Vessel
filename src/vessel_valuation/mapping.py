"""Field-driven conversions for ``VesselInputs``.

``VesselInputs`` (in ``schema.py``) is the single domain shape. This module is the
only place that enumerates its field names for cross-boundary mapping — repository,
``dcc.Store``, form display, and post-validation coercion all derive their field
lists from ``dataclasses.fields(VesselInputs)`` via the exports below.

Callers
-------
``vessel_inputs_kwargs`` / ``vessel_inputs_from_object``
    ``db.repository`` — silver ORM row ↔ domain.
``vessel_inputs_to_dict`` / ``vessel_inputs_from_dict``
    ``app.serialization`` — browser session store (JSON-safe dicts).
``vessel_inputs_to_form_raw_dict``
    ``app.serialization`` — manual form defaults before comma formatting.
``vessel_inputs_from_coerced_kwargs``
    ``validation.coercion.coerce_inputs`` — Tier 1 raw dict after structural rules.

``purchase_date`` is always serialized as an ISO ``YYYY-MM-DD`` string in dicts;
optional fields ``engine_type`` and ``co2_carbon_factor`` accept empty strings at
the store/form boundary and become ``None`` on the dataclass.
"""

import dataclasses
from datetime import date
from enum import StrEnum
from typing import cast

from vessel_valuation.schema import VesselInputs

_VESSEL_INPUT_FIELDS = dataclasses.fields(VesselInputs)


class VesselInputField(StrEnum):
    """``VesselInputs`` attribute names for typed cross-boundary mapping."""

    VESSEL_NAME = 'vessel_name'
    PURCHASE_PRICE = 'purchase_price'
    VESSEL_LIFE = 'vessel_life'
    RESIDUAL_VALUE = 'residual_value'
    LW_TONNAGE = 'lw_tonnage'
    REVENUE_PER_DAY = 'revenue_per_day'
    OFFHIRE_RATE = 'offhire_rate'
    OPEX_PER_DAY = 'opex_per_day'
    DRYDOCK_CAPEX = 'drydock_capex'
    DRYDOCK_FREQUENCY = 'drydock_frequency'
    UPGRADES_CAPEX = 'upgrades_capex'
    INFLATION_RATE = 'inflation_rate'
    DISCOUNT_RATE = 'discount_rate'
    DAYS_OF_YEAR = 'days_of_year'
    TEU_SIZE = 'teu_size'
    PURCHASE_DATE = 'purchase_date'
    ENGINE_TYPE = 'engine_type'
    CO2_CARBON_FACTOR = 'co2_carbon_factor'


# Stable field-name tuple — use for upload headers, column checks, and parity tests.
VESSEL_INPUT_FIELD_NAMES: tuple[str, ...] = tuple(f.name for f in _VESSEL_INPUT_FIELDS)

FormRawValue = str | int | float | None
VesselInputFormRawDict = dict[VesselInputField, FormRawValue]

# ``VesselInputRow`` columns that are persistence metadata, not part of the dataclass.
VESSEL_INPUT_ROW_META_COLUMNS: frozenset[str] = frozenset(
    {'id', 'submission_id', 'created_at'},
)


def vessel_inputs_kwargs(source: object) -> dict[str, object]:
    """Copy every ``VesselInputs`` field from ``source`` by attribute name.

    Parameters
    ----------
    source
        Any object with the same attribute names as ``VesselInputs`` (e.g. a
        dataclass instance or ``VesselInputRow``). Values are not copied or
        converted — callers that need JSON or strict typing use
        ``vessel_inputs_to_dict`` / ``vessel_inputs_from_dict`` instead.

    Returns
    -------
    dict[str, object]
        One entry per dataclass field, suitable for ``VesselInputRow(**...)`` or
        ``_build_vessel_inputs``.
    """
    return {field.name: getattr(source, field.name) for field in _VESSEL_INPUT_FIELDS}


def _build_vessel_inputs(kwargs: dict[str, object]) -> VesselInputs:
    """Construct ``VesselInputs`` from a complete, per-field-typed kwargs dict.

    Internal helper: callers must supply every field name and values already
    coerced to Python types (``date``, ``float``, ``int``, ``str``, or ``None``
    for optionals). Uses explicit casts so Pyright accepts construction from
    ``dict[str, object]`` (``VesselInputs(**kwargs)`` does not type-check).

    Parameters
    ----------
    kwargs
        Keys must match ``VESSEL_INPUT_FIELD_NAMES`` exactly.

    Returns
    -------
    VesselInputs
    """
    return VesselInputs(
        vessel_name=str(kwargs['vessel_name']),
        purchase_price=float(cast(float, kwargs['purchase_price'])),
        vessel_life=int(cast(int, kwargs['vessel_life'])),
        residual_value=float(cast(float, kwargs['residual_value'])),
        lw_tonnage=float(cast(float, kwargs['lw_tonnage'])),
        revenue_per_day=float(cast(float, kwargs['revenue_per_day'])),
        offhire_rate=float(cast(float, kwargs['offhire_rate'])),
        opex_per_day=float(cast(float, kwargs['opex_per_day'])),
        drydock_capex=float(cast(float, kwargs['drydock_capex'])),
        drydock_frequency=int(cast(int, kwargs['drydock_frequency'])),
        upgrades_capex=float(cast(float, kwargs['upgrades_capex'])),
        inflation_rate=float(cast(float, kwargs['inflation_rate'])),
        discount_rate=float(cast(float, kwargs['discount_rate'])),
        days_of_year=int(cast(int, kwargs['days_of_year'])),
        teu_size=int(cast(int, kwargs['teu_size'])),
        purchase_date=cast(date, kwargs['purchase_date']),
        engine_type=cast(str | None, kwargs['engine_type']),
        co2_carbon_factor=cast(float | None, kwargs['co2_carbon_factor']),
    )


def vessel_inputs_from_coerced_kwargs(kwargs: dict[str, object]) -> VesselInputs:
    """Build ``VesselInputs`` after Tier 1 coercion (validation layer).

    Parameters
    ----------
    kwargs
        Per-field values produced by ``coerce_inputs`` — must include every
        ``VesselInputs`` field name, no more and no less.

    Returns
    -------
    VesselInputs

    Raises
    ------
    ValueError
        If ``kwargs`` keys do not match the dataclass field set exactly.
    """
    if frozenset(kwargs) != frozenset(VESSEL_INPUT_FIELD_NAMES):
        raise ValueError('kwargs keys must match VesselInputs fields exactly')
    return _build_vessel_inputs(kwargs)


def vessel_inputs_from_object(source: object) -> VesselInputs:
    """Load ``VesselInputs`` from an ORM row or any attribute-compatible object.

    Parameters
    ----------
    source
        Typically ``VesselInputRow``; attribute names and types must already
        match the dataclass (SQLAlchemy returns native ``date`` / ``float`` / …).

    Returns
    -------
    VesselInputs
    """
    return _build_vessel_inputs(vessel_inputs_kwargs(source))


def vessel_inputs_to_dict(inputs: VesselInputs) -> dict[str, object]:
    """Serialize ``VesselInputs`` for JSON (e.g. ``dcc.Store``).

    Parameters
    ----------
    inputs
        Validated domain instance.

    Returns
    -------
    dict[str, object]
        Flat dict with one key per field. ``purchase_date`` is an ISO date string;
        other values match the in-memory types (numbers stay numeric).
    """
    data = vessel_inputs_kwargs(inputs)
    data['purchase_date'] = inputs.purchase_date.isoformat()
    return data


def vessel_inputs_to_form_raw_dict(
    inputs: VesselInputs,
) -> VesselInputFormRawDict:
    """Map ``VesselInputs`` to form-friendly values before comma formatting.

    Dash text inputs expect strings for empty optionals and an ISO date string
    for ``purchase_date``. Apply ``format_form_values_for_display`` in
    ``app.serialization`` after this step.

    Parameters
    ----------
    inputs
        Validated domain instance.

    Returns
    -------
    VesselInputFormRawDict
        One entry per field; ``engine_type`` and ``co2_carbon_factor`` use ``''``
        when unset.
    """
    values: VesselInputFormRawDict = {}
    for field in _VESSEL_INPUT_FIELDS:
        field_key = VesselInputField(field.name)
        value = getattr(inputs, field.name)
        if field_key is VesselInputField.PURCHASE_DATE:
            values[field_key] = value.isoformat()
        elif field_key is VesselInputField.ENGINE_TYPE:
            values[field_key] = value or ''
        elif field_key is VesselInputField.CO2_CARBON_FACTOR:
            values[field_key] = value if value is not None else ''
        else:
            values[field_key] = value
    return values


def _require_float(data: dict[str, object], key: str) -> float:
    """Parse one store/form numeric field; raise if not coercible to float."""
    value = data[key]
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError(f'{key} must be numeric')


def _require_int(data: dict[str, object], key: str) -> int:
    """Parse one store/form integer field; reject bools masquerading as ints."""
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


def _optional_str(value: object) -> str | None:
    """Map empty store/form strings to ``None`` for optional string fields."""
    if value is None or value == '':
        return None
    return str(value)


def _optional_float(value: object) -> float | None:
    """Map empty store/form strings to ``None`` for optional numeric fields."""
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return None


def _parse_purchase_date(raw: object, key: str) -> date:
    """Parse ``purchase_date`` from ISO string or pass through ``date`` instances."""
    if isinstance(raw, str):
        return date.fromisoformat(raw)
    if isinstance(raw, date):
        return raw
    raise TypeError(f'{key} must be an ISO date string or date')


def vessel_inputs_from_dict(data: dict[str, object]) -> VesselInputs:
    """Deserialize ``VesselInputs`` from a flat dict (e.g. ``dcc.Store``).

    Iterates ``dataclasses.fields(VesselInputs)`` so new schema fields are picked
    up automatically; only ``purchase_date`` and the two optionals need special
    parsing rules.

    Parameters
    ----------
    data
        JSON-round-tripped dict, typically from ``vessel_inputs_to_dict``.

    Returns
    -------
    VesselInputs

    Raises
    ------
    TypeError
        If a value cannot be coerced to the field's type.
    KeyError
        If a required field key is missing.
    """
    kwargs: dict[str, object] = {}
    for field in _VESSEL_INPUT_FIELDS:
        name = field.name
        if field.type is date:
            kwargs[name] = _parse_purchase_date(data[name], name)
        elif field.type is float:
            kwargs[name] = _require_float(data, name)
        elif field.type is int:
            kwargs[name] = _require_int(data, name)
        elif field.type is str:
            kwargs[name] = str(data[name])
        elif name == VesselInputField.ENGINE_TYPE:
            kwargs[name] = _optional_str(data.get(name))
        elif name == VesselInputField.CO2_CARBON_FACTOR:
            kwargs[name] = _optional_float(data.get(name))
        else:
            raise TypeError(f'unhandled VesselInputs field {name!r}')
    return _build_vessel_inputs(kwargs)
