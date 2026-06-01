"""Structural validation — type, presence, and range checks on raw input dicts.

Structural rules run **before** coercion to ``VesselInputs``. Any failure
blocks computation: the UI shows errors and ``ValidationResult.inputs`` is
``None``. These checks answer: "Can we parse this record and run the DCF?"

Examples: required fields, Excel sentinels (``#VALUE!``), numeric coercibility,
rate bounds, ``days_of_year == 365``.
"""

from vessel_valuation.validation.coercion import to_date, to_float, to_int
from vessel_valuation.validation.types import RawRule


def _positive_float_rule(code: str, key: str, label: str) -> RawRule:
    def check(raw: dict[str, object]) -> bool:
        v = to_float(raw, key)
        return v is not None and v > 0

    return RawRule(code, f'{label} must be a positive number', check)


def _non_negative_float_rule(code: str, key: str, label: str) -> RawRule:
    def check(raw: dict[str, object]) -> bool:
        v = to_float(raw, key)
        return v is not None and v >= 0

    return RawRule(code, f'{label} must be zero or a positive number', check)


def _rate_rule(
    code: str,
    key: str,
    label: str,
    strictly_positive: bool = False,
) -> RawRule:
    lo = '> 0' if strictly_positive else '>= 0'
    msg = f'{label} must be {lo} and < 1 (e.g. 0.10 for 10%)'

    def check(raw: dict[str, object]) -> bool:
        v = to_float(raw, key)
        if v is None:
            return False
        return (v > 0 if strictly_positive else v >= 0) and v < 1

    return RawRule(code, msg, check)


STRUCTURAL_RULES = [
    RawRule(
        'V-001',
        'Vessel name is required',
        lambda r: bool(str(r.get('vessel_name', '')).strip()),
    ),
    _positive_float_rule('V-002', 'purchase_price', 'Purchase price'),
    RawRule(
        'V-003',
        'Vessel life must be a whole number of at least 1 year',
        lambda r: (to_int(r, 'vessel_life') or 0) >= 1,
    ),
    _positive_float_rule('V-004', 'lw_tonnage', 'Light weight tonnage (LWT)'),
    _positive_float_rule('V-016', 'residual_value', 'Residual value'),
    _positive_float_rule('V-005', 'revenue_per_day', 'Revenue per day'),
    _rate_rule('V-006', 'offhire_rate', 'Off-hire rate'),
    _positive_float_rule('V-007', 'opex_per_day', 'OpEx per day'),
    _positive_float_rule('V-008', 'drydock_capex', 'Drydock CapEx'),
    RawRule(
        'V-009',
        'Drydock frequency must be a whole number of at least 1 year',
        lambda r: (to_int(r, 'drydock_frequency') or 0) >= 1,
    ),
    _non_negative_float_rule('V-010', 'upgrades_capex', 'Upgrades CapEx'),
    _rate_rule('V-011', 'inflation_rate', 'Inflation rate'),
    _rate_rule('V-012', 'discount_rate',
               'Discount rate', strictly_positive=True),
    RawRule(
        'V-013',
        'Days of year must equal 365 — no other value is supported',
        lambda r: to_int(r, 'days_of_year') == 365,
    ),
    RawRule(
        'V-014',
        'TEU size must be a positive whole number',
        lambda r: (to_int(r, 'teu_size') or 0) > 0,
    ),
    RawRule(
        'V-015',
        'Purchase date is required (YYYY-MM-DD or Excel date)',
        lambda r: to_date(r, 'purchase_date') is not None,
    ),
]
