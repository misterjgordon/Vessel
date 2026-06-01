"""Input validation — Tier 1 (type coercion) and Tier 2 (business rules).

Two-stage flow:
  raw dict  →  Tier 1 rules  →  VesselInputs (typed)  →  Tier 2 rules
                 (errors)                                  (warnings)

Tier 1 collects type and structural errors that prevent computation.
If any Tier 1 rule fails, coercion is aborted and ValidationResult.inputs
is None. Tier 2 runs only on a successfully coerced VesselInputs and
produces advisory warnings the user may override.
"""

import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from vessel_valuation.case_study_benchmarks import load_case_study_pp_teu_benchmarks
from vessel_valuation.schema import DEFAULT_VALIDATION_THRESHOLDS
from vessel_valuation.schema import ValidationThresholds
from vessel_valuation.schema import VesselInputs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SENTINELS: frozenset[str] = frozenset(
    {'#value!', '#n/a', '#ref!', '#div/0!', '#null!', 'n/a', '-', ''}
)

# Purchase-price÷TEU ratio defaults — medians from case-study sample sheet (see data/*.json).
_CASE_STUDY_PP_TEU_BENCHMARKS: dict[int, float] = load_case_study_pp_teu_benchmarks()

_TEU_REVENUE_SEEDS: dict[int, float] = {
    7000: 40_000.0,
    8000: 45_000.0,
    10000: 50_000.0,
    12000: 54_000.0,
}

# Tier 2 purchase-price and revenue benchmarks key on TEU rounded to this step.
TEU_BUCKET_ROUNDING = 1000


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

    pd = _to_date(raw, 'purchase_date')
    assert pd is not None, 'purchase_date should be valid after Tier 1'

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
    _positive_float_rule('V-016', 'residual_value', 'Residual value'),
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


def nearest_teu_bucket(teu: int) -> int:
    """Round TEU to the nearest ``TEU_BUCKET_ROUNDING`` step for benchmark lookup."""
    return round(teu / TEU_BUCKET_ROUNDING) * TEU_BUCKET_ROUNDING


def vessel_inputs_identity(inputs: VesselInputs) -> tuple[str, date, int]:
    """Return normalized identity for duplicate detection and peer matching."""
    return (inputs.vessel_name.strip().casefold(), inputs.purchase_date, inputs.teu_size)


def pp_teu_factor(purchase_price: float, teu_size: int) -> float:
    """Purchase-price÷TEU ratio: how many times purchase price exceeds TEU count."""
    return purchase_price / teu_size


def format_pp_teu_ratio(value: float) -> str:
    """Format a purchase-price÷TEU ratio for display (unitless multiple, not currency)."""
    return f'{value:,.0f}×'


def median_pp_teu_factor(inputs_list: list[VesselInputs]) -> dict[int, float]:
    """Median purchase-price÷TEU ratio by exact TEU when at least two vessels share that size."""
    by_teu: dict[int, list[float]] = {}
    for inp in inputs_list:
        by_teu.setdefault(inp.teu_size, []).append(pp_teu_factor(inp.purchase_price, inp.teu_size))
    return {teu: statistics.median(factors) for teu, factors in by_teu.items() if len(factors) >= 2}


def _resolved_pp_teu_factor_benchmarks(
    overrides: dict[int, float] | None,
) -> dict[int, float]:
    """Case-study PP÷TEU ratios merged with DB fleet overrides (exact TEU keys only)."""
    merged = dict(_CASE_STUDY_PP_TEU_BENCHMARKS)
    if overrides:
        merged.update(overrides)
    return merged


def _expected_pp_teu_factor(teu: int, benchmarks: dict[int, float]) -> float | None:
    """Return benchmark purchase-price÷TEU ratio for ``teu`` (exact, then rounded bucket)."""
    if teu in benchmarks:
        return benchmarks[teu]
    bucket = nearest_teu_bucket(teu)
    return benchmarks.get(bucket)


def _expected_revenue(teu: int) -> float | None:
    return _TEU_REVENUE_SEEDS.get(nearest_teu_bucket(teu))


def _pp_teu_factor_warning(
    inputs: VesselInputs,
    pp_teu_factor_benchmarks: dict[int, float],
    thresholds: ValidationThresholds,
) -> str | None:
    """Warn when purchase-price÷TEU ratio is outside ±tolerance of the TEU-class benchmark."""
    expected = _expected_pp_teu_factor(inputs.teu_size, pp_teu_factor_benchmarks)
    if expected is None:
        return None
    actual = pp_teu_factor(inputs.purchase_price, inputs.teu_size)
    tol = thresholds.price_tolerance
    lo, hi = expected * (1 - tol), expected * (1 + tol)
    if lo <= actual <= hi:
        return None
    return (
        f'Purchase-price÷TEU ratio {format_pp_teu_ratio(actual)} is outside the expected '
        f'±{tol:.0%} range for {inputs.teu_size:,} TEU vessels '
        f'({format_pp_teu_ratio(lo)} – {format_pp_teu_ratio(hi)})'
    )


def _teu_revenue_warning(
    inputs: VesselInputs,
    thresholds: ValidationThresholds,
) -> str | None:
    """Return a warning string if revenue/day is outside the TEU benchmark band."""
    expected = _expected_revenue(inputs.teu_size)
    if expected is None:
        return None
    band = thresholds.revenue_band
    if abs(inputs.revenue_per_day - expected) > band:
        lo, hi = expected - band, expected + band
        return (
            f'Revenue per day ${inputs.revenue_per_day:,.0f} is outside the expected '
            f'range for {inputs.teu_size} TEU vessels (${lo:,.0f} – ${hi:,.0f})'
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def tier2_warnings(
    inputs: VesselInputs,
    pp_teu_factor_benchmarks: dict[int, float] | None = None,
    thresholds: ValidationThresholds | None = None,
) -> list[str]:
    """Run Tier 2 rules on a validated VesselInputs; return a list of warnings.

    Parameters
    ----------
    inputs
        Validated vessel inputs — must have passed Tier 1.
    pp_teu_factor_benchmarks
        Exact TEU → median PP÷TEU from saved fleet (2+ peers). Merged over
        case-study defaults when the database has insufficient peers.
    thresholds
        TEU benchmark warning bands. Uses ``DEFAULT_VALIDATION_THRESHOLDS``
        when None.
    """
    active_thresholds = thresholds if thresholds is not None else DEFAULT_VALIDATION_THRESHOLDS
    benchmarks = _resolved_pp_teu_factor_benchmarks(pp_teu_factor_benchmarks)
    warnings = [rule.message for rule in TIER2_RULES if not rule.check(inputs)]
    factor_warn = _pp_teu_factor_warning(inputs, benchmarks, active_thresholds)
    if factor_warn:
        warnings.append(factor_warn)
    revenue_warn = _teu_revenue_warning(inputs, active_thresholds)
    if revenue_warn:
        warnings.append(revenue_warn)
    return warnings


def validate(
    raw: dict[str, object],
    pp_teu_factor_benchmarks: dict[int, float] | None = None,
    thresholds: ValidationThresholds | None = None,
) -> ValidationResult:
    """Run Tier 1 then Tier 2 validation against one raw vessel record.

    Parameters
    ----------
    raw
        Dict with keys matching VesselInputs field names. Produced by
        the manual form or file_parser before any coercion.
    pp_teu_factor_benchmarks
        Exact TEU → median PP÷TEU from saved fleet (2+ peers). Case-study
        defaults apply when the database has no peer median for that TEU.
    thresholds
        TEU benchmark warning bands. Uses ``DEFAULT_VALIDATION_THRESHOLDS``
        when None.

    Returns
    -------
    ValidationResult
        errors: Tier 1 failures (inputs is None if non-empty).
        warnings: Tier 2 advisories (inputs is populated regardless).
        inputs: Typed VesselInputs if Tier 1 passed, else None.
    """
    active_thresholds = thresholds if thresholds is not None else DEFAULT_VALIDATION_THRESHOLDS
    errors: list[str] = [rule.message for rule in TIER1_RULES if not rule.check(raw)]

    if errors:
        empty_warnings: list[str] = []
        return ValidationResult(errors=errors, warnings=empty_warnings, inputs=None)

    inputs = _coerce_inputs(raw)
    benchmarks = _resolved_pp_teu_factor_benchmarks(pp_teu_factor_benchmarks)

    warnings: list[str] = [rule.message for rule in TIER2_RULES if not rule.check(inputs)]

    factor_warn = _pp_teu_factor_warning(inputs, benchmarks, active_thresholds)
    if factor_warn:
        warnings.append(factor_warn)

    revenue_warn = _teu_revenue_warning(inputs, active_thresholds)
    if revenue_warn:
        warnings.append(revenue_warn)

    empty_errors: list[str] = []
    return ValidationResult(errors=empty_errors, warnings=warnings, inputs=inputs)
