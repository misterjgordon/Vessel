"""Type coercion helpers — convert raw dict values to typed ``VesselInputs`` fields."""

from datetime import date, datetime

from vessel_valuation.schema import VesselInputs
from vessel_valuation.validation.types import SENTINELS


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

    pd = to_date(raw, 'purchase_date')
    assert pd is not None, 'purchase_date should be valid after structural validation'

    return VesselInputs(
        vessel_name=str(raw.get('vessel_name', '')).strip(),
        purchase_price=req_float('purchase_price'),
        vessel_life=req_int('vessel_life'),
        residual_value=req_float('residual_value'),
        lw_tonnage=req_float('lw_tonnage'),
        revenue_per_day=req_float('revenue_per_day'),
        offhire_rate=req_float('offhire_rate'),
        opex_per_day=req_float('opex_per_day'),
        drydock_capex=req_float('drydock_capex'),
        drydock_frequency=req_int('drydock_frequency'),
        upgrades_capex=req_float('upgrades_capex'),
        inflation_rate=req_float('inflation_rate'),
        discount_rate=req_float('discount_rate'),
        days_of_year=req_int('days_of_year'),
        teu_size=req_int('teu_size'),
        purchase_date=pd,
        engine_type=str(raw['engine_type']) if raw.get(
            'engine_type') else None,
        co2_carbon_factor=to_float(raw, 'co2_carbon_factor'),
    )
