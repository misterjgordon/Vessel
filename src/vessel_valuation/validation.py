"""Input validation — Tier 1 (type coercion) and Tier 2 (business rules).

Two-stage flow:
  raw dict  →  Tier 1 rules  →  VesselInputs (typed)  →  Tier 2 rules
                 (errors)                                  (warnings)

Tier 1 collects type and structural errors that prevent computation.
If any Tier 1 rule fails, coercion is aborted and ValidationResult.inputs
is None. Tier 2 runs only on a successfully coerced VesselInputs and
produces advisory warnings the user may override.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from vessel_valuation.schema import SCRAP_RATE_PER_TONNE, VesselInputs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SENTINELS: frozenset[str] = frozenset(
    {'#value!', '#n/a', '#ref!', '#div/0!', '#null!', 'n/a', '-', ''}
)

REVENUE_BAND: float = 5_000.0
PRICE_TOLERANCE: float = 0.10

# Hardcoded seed benchmarks — derived from the 9 valid sample vessels.
# Replaced by live DB medians (via teu_medians parameter) after Phase 6.
_TEU_PRICE_SEEDS: dict[int, float] = {
    7000: 80_000_000.0,
    8000: 90_000_000.0,
    10000: 100_000_000.0,
    12000: 115_000_000.0,
}
_TEU_REVENUE_SEEDS: dict[int, float] = {
    7000: 40_000.0,
    8000: 45_000.0,
    10000: 50_000.0,
    12000: 54_000.0,
}


# ---------------------------------------------------------------------------
# Rule types
# ---------------------------------------------------------------------------


@dataclass
class RawRule:
    """Tier 1 rule — operates on the raw input dict before type coercion."""

    code: str
    message: str
    check: Callable[[dict[str, object]], bool]


@dataclass
class InputRule:
    """Tier 2 rule — operates on a validated VesselInputs instance."""

    code: str
    message: str
    check: Callable[[VesselInputs], bool]


@dataclass
class ValidationResult:
    """Outcome of running both validation tiers against one vessel record."""

    errors: list[str]
    warnings: list[str]
    inputs: VesselInputs | None


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def _is_sentinel(v: object) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in SENTINELS)


def _to_float(raw: dict[str, object], key: str) -> float | None:
    v = raw.get(key)
    if _is_sentinel(v):
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_int(raw: dict[str, object], key: str) -> int | None:
    v = _to_float(raw, key)
    return None if v is None else int(round(v))


def _to_date(raw: dict[str, object], key: str) -> date | None:
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


def _coerce_inputs(raw: dict[str, object]) -> VesselInputs:
    """Convert a Tier-1-validated raw dict to VesselInputs.

    Only call after all Tier 1 rules have passed. The local helpers
    assert non-None, which should always hold at this point.
    """

    def req_float(key: str) -> float:
        v = _to_float(raw, key)
        assert v is not None, f'{key} should be valid after Tier 1'
        return v

    def req_int(key: str) -> int:
        v = _to_int(raw, key)
        assert v is not None, f'{key} should be valid after Tier 1'
        return v

    lw = req_float('lw_tonnage')
    rv = _to_float(raw, 'residual_value')
    residual = rv if rv is not None else lw * SCRAP_RATE_PER_TONNE

    pd = _to_date(raw, 'purchase_date')
    assert pd is not None, 'purchase_date should be valid after Tier 1'

    return VesselInputs(
        vessel_name=str(raw.get('vessel_name', '')).strip(),
        purchase_price=req_float('purchase_price'),
        vessel_life=req_int('vessel_life'),
        residual_value=residual,
        lw_tonnage=lw,
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
        engine_type=str(raw['engine_type']) if raw.get('engine_type') else None,
        co2_carbon_factor=_to_float(raw, 'co2_carbon_factor'),
    )


# ---------------------------------------------------------------------------
# Rule factories — avoid repeating identical check patterns
# ---------------------------------------------------------------------------


def _positive_float_rule(code: str, key: str, label: str) -> RawRule:
    def check(raw: dict[str, object]) -> bool:
        v = _to_float(raw, key)
        return v is not None and v > 0

    return RawRule(code, f'{label} must be a positive number', check)


def _non_negative_float_rule(code: str, key: str, label: str) -> RawRule:
    def check(raw: dict[str, object]) -> bool:
        v = _to_float(raw, key)
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
        v = _to_float(raw, key)
        if v is None:
            return False
        return (v > 0 if strictly_positive else v >= 0) and v < 1

    return RawRule(code, msg, check)


# ---------------------------------------------------------------------------
# Tier 1 rule registry
# ---------------------------------------------------------------------------

TIER1_RULES: list[RawRule] = [
    RawRule(
        'V-001',
        'Vessel name is required',
        lambda r: bool(str(r.get('vessel_name', '')).strip()),
    ),
    _positive_float_rule('V-002', 'purchase_price', 'Purchase price'),
    RawRule(
        'V-003',
        'Vessel life must be a whole number of at least 1 year',
        lambda r: (_to_int(r, 'vessel_life') or 0) >= 1,
    ),
    _positive_float_rule('V-004', 'lw_tonnage', 'Light weight tonnage (LWT)'),
    _positive_float_rule('V-005', 'revenue_per_day', 'Revenue per day'),
    _rate_rule('V-006', 'offhire_rate', 'Off-hire rate'),
    _positive_float_rule('V-007', 'opex_per_day', 'OpEx per day'),
    _positive_float_rule('V-008', 'drydock_capex', 'Drydock CapEx'),
    RawRule(
        'V-009',
        'Drydock frequency must be a whole number of at least 1 year',
        lambda r: (_to_int(r, 'drydock_frequency') or 0) >= 1,
    ),
    _non_negative_float_rule('V-010', 'upgrades_capex', 'Upgrades CapEx'),
    _rate_rule('V-011', 'inflation_rate', 'Inflation rate'),
    _rate_rule('V-012', 'discount_rate', 'Discount rate', strictly_positive=True),
    RawRule(
        'V-013',
        'Days of year must equal 365 — no other value is supported',
        lambda r: _to_int(r, 'days_of_year') == 365,
    ),
    RawRule(
        'V-014',
        'TEU size must be a positive whole number',
        lambda r: (_to_int(r, 'teu_size') or 0) > 0,
    ),
    RawRule(
        'V-015',
        'Purchase date is required (YYYY-MM-DD or Excel date)',
        lambda r: _to_date(r, 'purchase_date') is not None,
    ),
    RawRule(
        'V-016',
        'Residual value, when provided, must be a non-negative number',
        lambda r: (
            r.get('residual_value') is None
            or _is_sentinel(r.get('residual_value'))
            or (_to_float(r, 'residual_value') or -1) >= 0
        ),
    ),
]


# ---------------------------------------------------------------------------
# Tier 2 rule registry
# ---------------------------------------------------------------------------

TIER2_RULES: list[InputRule] = [
    InputRule(
        'W-001',
        'Residual value equals or exceeds the purchase price — likely a data error',
        lambda v: v.residual_value < v.purchase_price,
    ),
    InputRule(
        'W-002',
        (
            'Effective daily revenue (after off-hire) is below OpEx per day — '
            'vessel loses money on every operating day'
        ),
        lambda v: v.revenue_per_day * (1 - v.offhire_rate) >= v.opex_per_day,
    ),
]


# ---------------------------------------------------------------------------
# TEU benchmark helpers (purchase price and revenue range checks)
# ---------------------------------------------------------------------------


def _nearest_teu_bucket(teu: int) -> int:
    """Round TEU to the nearest 500 for benchmark lookup."""
    return round(teu / 500) * 500


def _expected_price(teu: int, medians: dict[int, float]) -> float | None:
    """Return median purchase price for the TEU bucket, or None if unknown."""
    return medians.get(_nearest_teu_bucket(teu))


def _expected_revenue(teu: int) -> float | None:
    return _TEU_REVENUE_SEEDS.get(_nearest_teu_bucket(teu))


def _teu_price_warning(
    inputs: VesselInputs,
    teu_medians: dict[int, float],
) -> str | None:
    """Return a warning string if purchase price is outside TEU benchmark ±10%."""
    expected = _expected_price(inputs.teu_size, teu_medians)
    if expected is None:
        return None
    lo, hi = expected * (1 - PRICE_TOLERANCE), expected * (1 + PRICE_TOLERANCE)
    if not lo <= inputs.purchase_price <= hi:
        return (
            f'Purchase price ${inputs.purchase_price:,.0f} is outside the expected '
            f'±{PRICE_TOLERANCE:.0%} range for {inputs.teu_size} TEU vessels '
            f'(${lo:,.0f} – ${hi:,.0f})'
        )
    return None


def _teu_revenue_warning(inputs: VesselInputs) -> str | None:
    """Return a warning string if revenue/day is outside the TEU benchmark ±$5k."""
    expected = _expected_revenue(inputs.teu_size)
    if expected is None:
        return None
    if abs(inputs.revenue_per_day - expected) > REVENUE_BAND:
        lo, hi = expected - REVENUE_BAND, expected + REVENUE_BAND
        return (
            f'Revenue per day ${inputs.revenue_per_day:,.0f} is outside the expected '
            f'range for {inputs.teu_size} TEU vessels (${lo:,.0f} – ${hi:,.0f})'
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate(
    raw: dict[str, object],
    teu_medians: dict[int, float] | None = None,
) -> ValidationResult:
    """Run Tier 1 then Tier 2 validation against one raw vessel record.

    Parameters
    ----------
    raw
        Dict with keys matching VesselInputs field names. Produced by
        the manual form or file_parser before any coercion.
    teu_medians
        TEU-bucket → median purchase price from the DB (vessel.benchmarks).
        When None, falls back to hardcoded seed benchmarks from sample data.

    Returns
    -------
    ValidationResult
        errors: Tier 1 failures (inputs is None if non-empty).
        warnings: Tier 2 advisories (inputs is populated regardless).
        inputs: Typed VesselInputs if Tier 1 passed, else None.
    """
    errors: list[str] = [rule.message for rule in TIER1_RULES if not rule.check(raw)]

    if errors:
        empty_warnings: list[str] = []
        return ValidationResult(errors=errors, warnings=empty_warnings, inputs=None)

    inputs = _coerce_inputs(raw)
    medians = teu_medians if teu_medians is not None else _TEU_PRICE_SEEDS

    warnings: list[str] = [rule.message for rule in TIER2_RULES if not rule.check(inputs)]

    price_warn = _teu_price_warning(inputs, medians)
    if price_warn:
        warnings.append(price_warn)

    revenue_warn = _teu_revenue_warning(inputs)
    if revenue_warn:
        warnings.append(revenue_warn)

    empty_errors: list[str] = []
    return ValidationResult(errors=empty_errors, warnings=warnings, inputs=inputs)
