"""Business-rule validation — plausibility checks on coerced ``VesselInputs``.

Business rules run **after** structural validation and coercion. Failures
produce advisory warnings only: the user may proceed to compute. These checks
answer: "Does this vessel look economically plausible?"

Each rule is one ``BusinessRule`` instance in ``BUSINESS_RULES``. The runner
evaluates every entry against ``RuleContext`` (benchmarks + thresholds).
"""

import statistics
from datetime import date

from vessel_valuation.case_study_benchmarks import load_case_study_pp_teu_benchmarks
from vessel_valuation.schema import (
    DEFAULT_VALIDATION_THRESHOLDS,
    ValidationThresholds,
    VesselInputs,
)
from vessel_valuation.validation.types import BusinessRule, RuleContext

# Purchase-price÷TEU ratio defaults — medians from case-study sample sheet (see data/*.json).
_CASE_STUDY_PP_TEU_BENCHMARKS: dict[int, float] = load_case_study_pp_teu_benchmarks()

_TEU_REVENUE_SEEDS: dict[int, float] = {
    7000: 40_000.0,
    8000: 45_000.0,
    10000: 50_000.0,
    12000: 54_000.0,
}

# Business-rule purchase-price and revenue benchmarks key on TEU rounded to this step.
TEU_BUCKET_ROUNDING = 1000

_RESIDUAL_EXCEEDS_PURCHASE_MSG = (
    'Residual value equals or exceeds the purchase price — likely a data error'
)
_REVENUE_BELOW_OPEX_MSG = (
    'Effective daily revenue (after off-hire) is below OpEx per day — '
    'vessel loses money on every operating day'
)


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


def resolved_pp_teu_factor_benchmarks(
    overrides: dict[int, float] | None,
) -> dict[int, float]:
    """Case-study PP÷TEU ratios merged with DB fleet overrides (exact TEU keys only)."""
    merged = dict(_CASE_STUDY_PP_TEU_BENCHMARKS)
    if overrides:
        merged.update(overrides)
    return merged


def expected_pp_teu_factor(teu: int, benchmarks: dict[int, float]) -> float | None:
    """Return benchmark purchase-price÷TEU ratio for ``teu`` (exact, then rounded bucket)."""
    if teu in benchmarks:
        return benchmarks[teu]
    bucket = nearest_teu_bucket(teu)
    return benchmarks.get(bucket)


def expected_revenue(teu: int) -> float | None:
    """Return the seeded revenue-per-day benchmark for a TEU bucket, if known."""
    return _TEU_REVENUE_SEEDS.get(nearest_teu_bucket(teu))


def _warn_residual_below_purchase(inputs: VesselInputs, ctx: RuleContext) -> str | None:
    """W-001 — flag when residual equals or exceeds purchase price."""
    del ctx
    if inputs.residual_value < inputs.purchase_price:
        return None
    return _RESIDUAL_EXCEEDS_PURCHASE_MSG


def _warn_revenue_below_opex(inputs: VesselInputs, ctx: RuleContext) -> str | None:
    """W-002 — flag when effective daily revenue cannot cover daily OpEx."""
    del ctx
    effective_revenue = inputs.revenue_per_day * (1 - inputs.offhire_rate)
    if effective_revenue >= inputs.opex_per_day:
        return None
    return _REVENUE_BELOW_OPEX_MSG


def _warn_pp_teu_factor_band(inputs: VesselInputs, ctx: RuleContext) -> str | None:
    """W-003 — flag when purchase-price÷TEU ratio is outside the TEU-class band."""
    expected = expected_pp_teu_factor(inputs.teu_size, ctx.pp_teu_factor_benchmarks)
    if expected is None:
        return None
    actual = pp_teu_factor(inputs.purchase_price, inputs.teu_size)
    tol = ctx.thresholds.price_tolerance
    lo, hi = expected * (1 - tol), expected * (1 + tol)
    if lo <= actual <= hi:
        return None
    return (
        f'Purchase-price÷TEU ratio {format_pp_teu_ratio(actual)} is outside the expected '
        f'±{tol:.0%} range for {inputs.teu_size:,} TEU vessels '
        f'({format_pp_teu_ratio(lo)} – {format_pp_teu_ratio(hi)})'
    )


def _warn_teu_revenue_band(inputs: VesselInputs, ctx: RuleContext) -> str | None:
    """W-004 — flag when revenue/day is outside the TEU benchmark band."""
    expected = expected_revenue(inputs.teu_size)
    if expected is None:
        return None
    band = ctx.thresholds.revenue_band
    if abs(inputs.revenue_per_day - expected) <= band:
        return None
    lo, hi = expected - band, expected + band
    return (
        f'Revenue per day ${inputs.revenue_per_day:,.0f} is outside the expected '
        f'range for {inputs.teu_size} TEU vessels (${lo:,.0f} – ${hi:,.0f})'
    )


BUSINESS_RULES: list[BusinessRule] = [
    BusinessRule('W-001', 'residual_below_purchase', _warn_residual_below_purchase),
    BusinessRule('W-002', 'revenue_below_opex', _warn_revenue_below_opex),
    BusinessRule('W-003', 'pp_teu_factor_band', _warn_pp_teu_factor_band),
    BusinessRule('W-004', 'teu_revenue_band', _warn_teu_revenue_band),
]


def build_rule_context(
    pp_teu_factor_benchmarks: dict[int, float] | None = None,
    thresholds: ValidationThresholds | None = None,
) -> RuleContext:
    """Build injected context for one business-rule evaluation pass."""
    active_thresholds = thresholds if thresholds is not None else DEFAULT_VALIDATION_THRESHOLDS
    benchmarks = resolved_pp_teu_factor_benchmarks(pp_teu_factor_benchmarks)
    return RuleContext(
        pp_teu_factor_benchmarks=benchmarks,
        thresholds=active_thresholds,
    )


def business_rule_warnings(
    inputs: VesselInputs,
    pp_teu_factor_benchmarks: dict[int, float] | None = None,
    thresholds: ValidationThresholds | None = None,
) -> list[str]:
    """Run all business rules on a validated ``VesselInputs``; return advisory warnings.

    Parameters
    ----------
    inputs
        Coerced vessel inputs — must have passed structural validation.
    pp_teu_factor_benchmarks
        Exact TEU → median PP÷TEU from saved fleet (2+ peers). Merged over
        case-study defaults when the database has insufficient peers.
    thresholds
        TEU benchmark warning bands. Uses ``DEFAULT_VALIDATION_THRESHOLDS``
        when None.
    """
    ctx = build_rule_context(pp_teu_factor_benchmarks, thresholds)
    warnings: list[str] = []
    for rule in BUSINESS_RULES:
        msg = rule.warn(inputs, ctx)
        if msg:
            warnings.append(msg)
    return warnings
