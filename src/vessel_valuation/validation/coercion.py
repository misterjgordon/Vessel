"""Type coercion helpers — convert raw dict values to typed ``VesselInputs`` fields."""

import dataclasses
from datetime import date, datetime

from vessel_valuation.mapping import vessel_inputs_from_coerced_kwargs
from vessel_valuation.schema import VesselInputs
from vessel_valuation.validation.types import SENTINELS

_VESSEL_INPUT_FIELDS = dataclasses.fields(VesselInputs)


def is_sentinel(v: object) -> bool:
    """Return True when ``v`` is null or an Excel-style sentinel string."""
    return v is None or (isinstance(v, str) and v.strip().lower() in SENTINELS)


def to_float(raw: dict[str, object], key: str) -> float | None:
    """Coerce one raw dict value to float, or None when missing or invalid."""
    v = raw.get(key)
    if is_sentinel(v):
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def to_int(raw: dict[str, object], key: str) -> int | None:
    """Coerce one raw dict value to int, or None when missing or invalid."""
    v = to_float(raw, key)
    return None if v is None else int(round(v))


def to_date(raw: dict[str, object], key: str) -> date | None:
    """Coerce one raw dict value to ``date``, or None when missing or invalid."""
    v = raw.get(key)
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v.strip())
        except ValueError:
            pass
    return None


def coerce_inputs(raw: dict[str, object]) -> VesselInputs:
    """Convert a structurally validated raw dict to ``VesselInputs``.

    Only call after all structural rules have passed. Local helpers assert
    non-None, which should always hold at this point.
    """

    def req_float(key: str) -> float:
        v = to_float(raw, key)
        assert v is not None, f'{key} should be valid after structural validation'
        return v

    def req_int(key: str) -> int:
        v = to_int(raw, key)
        assert v is not None, f'{key} should be valid after structural validation'
        return v

    kwargs: dict[str, object] = {}
    for field in _VESSEL_INPUT_FIELDS:
        name = field.name
        if name == 'vessel_name':
            kwargs[name] = str(raw.get(name, '')).strip()
        elif name == 'purchase_date':
            pd = to_date(raw, name)
            assert pd is not None, 'purchase_date should be valid after structural validation'
            kwargs[name] = pd
        elif name == 'engine_type':
            kwargs[name] = str(raw[name]) if raw.get(name) else None
        elif name == 'co2_carbon_factor':
            kwargs[name] = to_float(raw, name)
        elif field.type is float:
            kwargs[name] = req_float(name)
        elif field.type is int:
            kwargs[name] = req_int(name)
        else:
            raise AssertionError(f'unhandled VesselInputs field {name!r}')

    return vessel_inputs_from_coerced_kwargs(kwargs)
